import os,argparse
import logging
import serial
from elf import Elf,SectionNameNotFoundError
import datetime 
from pysatl import Utils

def timestamp() -> str:
    now = datetime.datetime.now()
    return now.strftime('%Y%m%d-%H:%M:%S')

def cmtrace(binary, func_name,*, out_dir=None,setup_func_name=None):
    image = Elf(elf=args.binary, binutils_prefix='arm-none-eabi-')
    logging.debug(image.functions_by_name.keys())
    func = image.functions_by_name[func_name]
    func_start = func['start']
    func_last = func['last_ins_addr']

    if setup_func_name is None:
        setup_func_name = func_name

    setup_func = image.functions_by_name[setup_func_name]
    setup_func_start = setup_func['start']
    setup_func_last = setup_func['last_ins_addr']

    if setup_func != func:
        logging.info(f'{setup_func_name:20}: {setup_func_start:#08x} to {setup_func_last:#08x}')

    logging.info(f'{func_name:20}: {func_start:#08x} to {func_last:#08x}')

    outfile = f'{os.path.basename(binary)}-{setup_func_name}.cmtrace'
    if out_dir:
        outfile = os.path.join(out_dir,outfile)

    with serial.Serial(device_path, baudrate=115200, exclusive=True) as device:
        device.flush()
        device.reset_input_buffer()    

        def device_write32(x: int):
            device.write(x.to_bytes(4,byteorder='little'))
        
        rx_log = bytearray()
        def device_read(size: int = 1):
            nonlocal rx_log
            dat = device.read(size)
            rx_log += dat
            return dat
        
        def device_read32() -> int:
            return int.from_bytes(device_read(4),byteorder='little')
        
        with open(outfile,'wb') as f:
            def f_write32(x: int):
                f.write(x.to_bytes(4,byteorder='little'))
            def f_read32() -> int:
                return int.from_bytes(f.read(4),byteorder='little')

            device_write32(setup_func_start)
            hello = device_read(8)
            if hello != b'cmtrace\0':
                raise RuntimeError(f'hello = {hello} ({Utils.hexstr(hello)})')
            free_run_cycles = device_read32()
            logging.debug(f'{free_run_cycles} cycles measured in free run (includes setup and timer read)')
            cnt = 1
            last_pc = None
            last_cnt = 1
            ins_cnt=0
            ins_cnt_setup=0
            func_cycles=0
            is_setup=True
            ra_in_setup = 0xFFFFFFFF
            if func == setup_func:
                is_setup=False
            def add_instruction():
                nonlocal ins_cnt, ins_cnt_setup
                pc_cycles = cnt - last_cnt
                if is_setup:
                    ins_cnt_setup += 1
                    logging.debug(f'PC={last_pc:#08x}: {pc_cycles} {image.addresses[last_pc]['ins']} (setup)')
                else:
                    ins_cnt += 1
                    logging.info(f'PC={last_pc:#08x}: {pc_cycles} {image.addresses[last_pc]['ins']}')
                    f_write32(pc)
                    f_write32(pc_cycles)
            while True:
                cy = device_read32()
                if cy == 0xFFFFFFFF:
                    logging.debug('Received 0xFFFFFFFF, exit')
                    break
                if cy != cnt:
                    raise RuntimeError(f'cnt={cnt}, cy={cy} ({cy:#08x})\n{Utils.hexstr(rx_log)}')
                pc = device_read32()
                logging.debug(f'PC={pc:#08x}, cycle {cy}')
                if last_pc and last_pc != pc:
                    add_instruction()
                    if pc == func_start:
                        is_setup = False
                        ra_in_setup = last_pc + image.addresses[last_pc]['size']
                        logging.debug(f'{image.addresses[last_pc]}')
                        logging.debug(f'ra_in_setup={ra_in_setup:#08x}')
                    if pc == ra_in_setup:
                        is_setup = True
                    last_cnt = cnt
                cnt += 1
                if not is_setup:
                    func_cycles += 1
                last_pc = pc
            add_instruction()
            total_cycles = device_read32()
            if total_cycles != cnt:
                raise RuntimeError(f'cnt={cnt}, total_cycles={total_cycles}')
            print(f'{func_name}: {ins_cnt} instructions, {func_cycles} cycles')


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
        '--setup', default=None, help='Target setup function (must be void (*)(void))', type=str
    )
    parser.add_argument(
        '--out-dir', default=None, help='Path for output file (must be existing directory)', type=str
    )
        
    args = parser.parse_args()

    device_path = args.device

    logformat = '%(asctime)s.%(msecs)03d %(levelname)s:\t%(message)s'
    logdatefmt = '%Y-%m-%d %H:%M:%S'
    logging.basicConfig(level=args.log_level, format=logformat, datefmt=logdatefmt)

    cmtrace(args.binary, args.func, out_dir=args.out_dir, setup_func_name=args.setup)