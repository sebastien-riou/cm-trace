import argparse
from html import parser
import logging
from cmtrace import CmTrace, CustomScale
import os


def main():
    scriptname = os.path.basename(__file__)
    parser = argparse.ArgumentParser(scriptname)
    levels = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    parser.add_argument('--log-level', default='INFO', choices=levels)
    parser.add_argument('trace_path', metavar='trace-path', help='Path to the trace file', type=str)
    parser.add_argument('--percent-scale', default=False, help='Add a percentage scale', action='store_true')
    parser.add_argument('--custom-scale', default=None, help='Add a custom scale, you must specify a name', type=str)
    parser.add_argument('--scale-start', help='Start of the scale', type=int)
    parser.add_argument('--scale-end', help='End of the scale', type=int)
    parser.add_argument('--scale-first-addr', help='First address of the scale', type=str)
    parser.add_argument('--scale-last-addr', help='Last address of the scale', type=str)
    parser.add_argument('--scale-sep', default='|', help='Separator for the columns', type=str)

    args = parser.parse_args()

    logformat = '%(asctime)s.%(msecs)03d %(levelname)s:\t%(message)s'
    logdatefmt = '%Y-%m-%d %H:%M:%S'
    logging.basicConfig(level=args.log_level, format=logformat, datefmt=logdatefmt)

    trace = CmTrace.from_file(args.trace_path)
    logging.debug(f'{trace.instruction_count} instructions, {trace.total_cycles} cycles')
    scale = None
    if args.percent_scale:
        scale = CustomScale('%', 0, 100, list(trace.get_records()))
    if args.custom_scale:
        if args.scale_start is None or args.scale_end is None:
            parser.error('--scale-start and --scale-end are required for custom scale')
        first_addr = None
        last_addr = None
        if args.scale_first_addr is not None:
            first_addr = int(args.scale_first_addr, 16)
        if args.scale_last_addr is not None:
            last_addr = int(args.scale_last_addr, 16)
        scale = CustomScale(args.custom_scale, args.scale_start, args.scale_end, list(trace.get_records()), 
                            sep=args.scale_sep,
                            first_address=first_addr, last_address=last_addr)
    trace.dump(custom_scale=scale, sep=args.scale_sep)


if __name__ == '__main__':
    main()
