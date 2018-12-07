#!/usr/bin/python
import cmath
import math

import numpy as np
import svgpathtools


def avg_rms(ndarr):
    avg = np.average(ndarr)
    rms = np.sqrt(np.average(np.square(ndarr - avg)))
    return avg, rms


def all(arr, predicate):
    for el in arr:
        if not predicate(el):
            return False
    return True


def radius_center_from_bezier_segment(bz):
    ctrlvec1 = bz.control1 - bz.start  # point from start to ctrl1
    start_to_end_vect = bz.end - bz.start  # point from start to end

    ctrlvec2 = bz.control2 - bz.end  # point from end to ctrl2
    end_to_start_vect = bz.start - bz.end

    # angle of the circle segment is the angle between the inverse
    # of the ctrlvec2 vector (it's looking into the segment, but
    # when going from start to end, we are looking out of the
    # segment) and the ctrlvec1 vector
    angle = cmath.phase(-ctrlvec2 / ctrlvec1)

    # this r might become negative is angle_circle_sgment < 0, but
    # we use this to indicate the two different rotation angles, and
    # this fixes the rotation by *-1j or *1j in the line beneath
    r = abs(start_to_end_vect) / (2 * math.sin(angle / 2))
    vect_to_ctr = ctrlvec1 / abs(ctrlvec1) * r * 1j
    ctr = bz.start + vect_to_ctr

    angle1 = cmath.phase(ctrlvec1 * 1j)
    angle2 = cmath.phase(ctrlvec2 * -1j)

    return abs(r), ctr, angle1 * 180 / math.pi, angle2 * 180 / math.pi


def check_circle(path):
    if not all(path, lambda el: isinstance(el, svgpathtools.CubicBezier)):
        return False

    radii_center_angles = None
    try:
        radii_center_angles = [radius_center_from_bezier_segment(bz) for bz in path]
    except ZeroDivisionError:
        return False

    ###
    # absurd idea: check if the jitter on radius and center is acceptable
    # to call it a circle ;-)
    ###
    ndarr = np.array(radii_center_angles, dtype=complex)
    avg_r, rms_r = avg_rms(ndarr[:, 0])
    if np.abs(rms_r) >= 0.01 * np.abs(avg_r):
        print('Jitter >1% avg radius in radius determination -> not a circle.')
        return False
    avg_ctr, rms_ctr = avg_rms(ndarr[:, 1])
    if np.abs(rms_ctr) >= 0.01 * np.abs(avg_r):
        print('Jitter >1% radius in center determination -> not a circle.')
        return False

    r = np.abs(avg_r)
    ctr = avg_ctr
    return r, ctr


CIRCLES = dict()  # (point) -> radius
LINES = dict()  # (point) -> set(points)


def add_line(a, b):

    a = a.conjugate() # flip y
    b = b.conjugate()

    if not a in LINES:
        LINES[a] = set()
    if not b in LINES:
        LINES[b] = set()

    LINES[a].add(b)
    LINES[b].add(a)


def add_path(path):
    for el in path:
        if isinstance(el, svgpathtools.Line):
            add_line(el.start, el.end)
        elif isinstance(el, svgpathtools.QuadraticBezier) :
            t = np.linspace(0.0, 1.0, 10)
            t1 = np.square(1-t)
            t2 = 2*(1-t)*t
            t3 = np.square(t)
            p = el.start * t1 + el.control * t2 + el.end * t3

            for a, b in zip(p[:-1], p[1:]):
                add_line(a, b)

        elif isinstance(el, svgpathtools.CubicBezier):
            t = np.linspace(0.0, 1.0, 10)
            t1 = np.power(1 - t, 3)
            t2 = 3 * np.square(1 - t) * t
            t3 = 3 * np.square(t) * (1 - t)
            t4 = np.power(t, 3)
            p = el.start * t1 + el.control1 * t2 + el.control2 * t3 + el.end * t4

            for a, b in zip(p[:-1], p[1:]):
                add_line(a, b)
        else:
            raise RuntimeError('Path element must be line or CubicBezier, not ' + repr(el))


def get_min(arr, metric):
    """for a given array of elements, and a metric, return the
    element end the metric for this element where the metric is minimal"""
    min_metric = None
    min_element = None

    for el in arr:
        m = metric(el)
        if min_metric is None or m < min_metric:
            min_metric = m
            min_element = el

    return min_element, min_metric


def pt(c):
    x = np.rint(c.real)
    y = np.rint(c.imag)
    """ format a complex point as X,Y """
    return f'{x:.0f},{y:.0f}'


def ctr_span(arr):
    a = np.amin(arr)
    b = np.amax(arr)
    return 0.5 * (b + a), b - a


def calc_scale(points, oxmin, oymin, oxmax, oymax):
    coords = np.array(points)
    xctr, width = ctr_span(np.real(coords))
    yctr, height = ctr_span(np.imag(coords))

    oxctr, owidth = (oxmax + oxmin) / 2, oxmax - oxmin
    oyctr, oheight = (oymax + oymin) / 2, oymax - oymin

    s = min([owidth / width, oheight / height])
    offs = oxctr - xctr * s + (oyctr - yctr * s) * 1j

    return s, offs


def emit_lines(of, scale=1, offs=0.0):
    dir = 1.0
    p = 0.0

    # new segment
    while LINES:

        p, _ = get_min(LINES, lambda v: abs(v - p))
        print(f'PU{pt(p*scale+offs)};PD', end='', file=of)

#        print(f'New segment, start at {pt(p)}.')
#        print(f'  (neighbors are {LINES[p]})')

        while p in LINES:
            q, _ = get_min(LINES[p], lambda v: cmath.phase((v - p) / dir))
            dir = (q - p) / np.abs(q - p)

            x = q.real
            y = q.imag

            # remove line segments
            LINES[p].remove(q)
            LINES[q].remove(p)

            # last point?
            if LINES[q]:
                print(f'{pt(q*scale+offs)},', end='', file=of)
            else:
                print(f'{pt(q*scale+offs)};', file=of)

#            print(f' draw to {pt(q)}.')

            if not LINES[p]:
                del LINES[p]
            if not LINES[q]:
                del LINES[q]
            p = q


def emit_circles(of, scale=1.0, offs=0.0):
    p = 0.0

    while CIRCLES:
        p, _ = get_min(CIRCLES, lambda v: abs(v - p))
        print(p)
        print(f'Circle at {pt(p)}.')

        print(f'PU{pt(p*scale+offs)};', end='', file=of)
        for r in CIRCLES[p]:
            print(f'CI{r*scale};', end='', file=of)

        del CIRCLES[p]
        print(file=of)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('svgfile', metavar='SVGFILE',
                        help='SVG file to parse')
    parser.add_argument('hpglfile', metavar='HPGFILE', nargs='?',
                        help='HPGL file to output.')

    args = parser.parse_args()

    if args.hpglfile:
        of = open(args.hpglfile, 'wt')
    else:
        of = None

    paths, attributes = svgpathtools.svg2paths(args.svgfile)
    for p, a in zip(paths, attributes):
#        circle = check_circle(p)
#        if circle:
#            r, ctr = circle
#            if not ctr in CIRCLES:
#                CIRCLES[ctr] = set()
#            CIRCLES[ctr].add(r)
        add_path(p)

    all_coords = list(LINES.keys())
    for p in CIRCLES:
        for r in CIRCLES[p]:
            all_coords.append(p - (r + 0.1) * (1 + 1j))
            all_coords.append(p + (r + 0.1) * (1 + 1j))
    # metric A4 is X=0..11040 Y=7721
    s, offs = calc_scale(all_coords, 0, 0, 11040, 7721)


    print('IN;SP1;', file=of)
    emit_lines(of, s, offs)
    #    emit_circles(of, s, offs)

    print('PU0,0;IN;', file=of)


if __name__ == '__main__':
    main()
