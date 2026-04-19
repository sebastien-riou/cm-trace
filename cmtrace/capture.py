import argparse
import logging
from cmtrace import CmTrace
import serial
import os

if __name__ == "__main__":
    scriptname = os.path.basename(__file__)
    parser = argparse.ArgumentParser(scriptname)
    levels = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    parser.add_argument('--log-level', default='INFO', choices=levels)
    parser.add_argument(
        'device', metavar='device-path', default=None, help='Path to the serial device', type=str
    )
    parser.add_argument(
        'binary', default=None, help='Target binary (elf)', type=str
    )
    parser.add_argument(
        'func', default=None, help='Target function (must be void (*)(void), unless --setup is given)', type=str
    )
    parser.add_argument(
        '--setup', default='', help='Target setup function (must be void (*)(void))', type=str
    )
    parser.add_argument(
        '--out-dir', default=None, help='Path for output file (must be existing directory)', type=str
    )
        
    args = parser.parse_args()

    device_path = args.device

    logformat = '%(asctime)s.%(msecs)03d %(levelname)s:\t%(message)s'
    logdatefmt = '%Y-%m-%d %H:%M:%S'
    logging.basicConfig(level=args.log_level, format=logformat, datefmt=logdatefmt)

    tracer = CmTrace(args.binary, args.func, setup_func_name=args.setup)
    with serial.Serial(device_path, baudrate=115200, exclusive=True) as device:
        tracer.capture(device, out_dir=args.out_dir)