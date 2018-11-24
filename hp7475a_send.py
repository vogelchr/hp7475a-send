#!/usr/bin/python
import serial
import time

# answer to <ESC>.O Output Extended Status Information [Manual: 10-42]
EXT_STATUS_BUF_EMPTY = 0x08 # buffer empty
EXT_STATUS_VIEW = 0x10  # "view" button has been pressed, plotting suspended
EXT_STATUS_LEVER = 0x20 # paper lever raised, potting suspended

def inquire(tty, what) :
    tty.write(what)

    buf = bytearray()

    tty.write(b'\033.0')
    while True :
        c = tty.read(1)
        if not c :  # timeout
            return None
        if c == b'\r' :
            break
        buf += c
    return int(buf)

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', type=str, default='/dev/ttyS0',
                        metavar='TTY', help='Serial port (default: /dev/ttyS0)')
    parser.add_argument('-b', '--baud', type=int, default=9600,
                        metavar='N', help='Baudrate (default: 9600)')

    parser.add_argument('hpglfile')

    args = parser.parse_args()

    hpgl = open(args.hpglfile, 'rb')

    tty = serial.Serial(args.port, args.baud, timeout=2.0)

    # <ESC>.@<dec>;<dec>:
    #  1st parameter is buffer size 0..1024, optional
    #  2nd parameter is bit flags for operation mode
    #     0x01 : enable HW handhaking
    #     0x02 : ignored
    #     0x04 : monitor mode 1 if set, mode 0 if unset (for terminal)
    #     0x08 : 0: disable monitor mode, 1: enable monitor mode
    #     0x10 : 0: normal mode, 1: block mode
    tty.write(b'\033.@;0:')  # Plotter Configuration [Manual 10-27]
    tty.write(b'\033.Y')  # Plotter On [Manual 10-26]
    tty.write(b'\033.K') # abort graphics

    bufsz = inquire(tty, b'\033.L')
    print('Buffer size of plotter is', bufsz, 'bytes.')

    is_paused = False
    while True :
        status = inquire(tty, b'\033.O')
        if status is None :
            print('*** Error: timeout waiting for printer status (command ESC.O).')
            break

        if (status & (EXT_STATUS_VIEW | EXT_STATUS_LEVER)) :
            if not is_paused :
                print('*** Printer is viewing plot, pausing data.')
            is_paused = True
            time.sleep(5.0)
            continue
        else :
            if is_paused :
                print('*** Resuming data.')
            is_paused = False

        if not (status & EXT_STATUS_BUF_EMPTY) :
            print('*** Buffer not empty, waiting...')
            time.sleep(0.5)
            continue

        data = hpgl.read(bufsz)
        if len(data) == 0 :
            print('*** EOF reached, exiting.')
            break
        print('*** Writing', len(data), 'bytes to plotter.')
        tty.write(data)

if __name__ == '__main__':
    main()
