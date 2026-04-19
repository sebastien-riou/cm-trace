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
        'trace_path', metavar='trace-path', help='Path to the trace file', type=str
    )
    
    args = parser.parse_args()

    logformat = '%(asctime)s.%(msecs)03d %(levelname)s:\t%(message)s'
    logdatefmt = '%Y-%m-%d %H:%M:%S'
    logging.basicConfig(level=args.log_level, format=logformat, datefmt=logdatefmt)

    trace = CmTrace.from_file(args.trace_path)
    logging.debug(f'{trace.instruction_count} instructions, {trace.total_cycles} cycles')
    trace.dump()
    