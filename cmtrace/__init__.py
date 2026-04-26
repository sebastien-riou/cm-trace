import datetime
import logging
import os

from cmtrace.elf import Elf

try:
    from pysatl import Utils
except:  # noqa E722

    class Utils:
        @staticmethod
        def hexstr(b):
            return f'{b}'


def timestamp() -> str:
    now = datetime.datetime.now()
    return now.strftime('%Y%m%d-%H:%M:%S')


def write32(dst, x: int):
    dst.write(x.to_bytes(4, byteorder='little'))


def read32(src) -> int:
    return int.from_bytes(src.read(4), byteorder='little')


def write_str(dst, s: str):
    write32(dst, len(s))
    dst.write(s.encode())


def read_str(src) -> str:
    size = read32(src)
    return src.read(size).decode()


class CustomScale(object):
    @property
    def name(self):
        return self._name
    
    def __init__(self, name, start, end, records,*,sep='|',first_address=None,last_address=None):
        self._name = name
        self._start = start
        self._end = end
        self._sep = sep
        if first_address:
            self._first_address = first_address
        else:
            self._first_address = records[0]['pc']
        if last_address:
            self._last_address = last_address
        else:
            self._last_address = records[-1]['pc']
        scy = 0
        for r in records:
            if r['pc'] == self._first_address:
                self._range_first_cycle = scy
            scy += r['cycles']
            if r['pc'] == self._last_address:
                self._range_last_cycle = scy - 1 
            
        self._scale = (end - start) / (self._range_last_cycle+1 - self._range_first_cycle)
        self._padlen = len(name+' first')

    def header(self):
        first = f'{self._name} first'
        last = f'{self._name} last'
        return f'{self._sep}{first:>{self._padlen}}{self._sep}{last:>{self._padlen}}'
    
    def instruction(self,first_cycle, last_cycle):
        if first_cycle < self._range_first_cycle or last_cycle > self._range_last_cycle:
            return f'{self._sep}{'':>{self._padlen}}{self._sep}{'':>{self._padlen}}'
        start_offset_in_cycles = first_cycle - self._range_first_cycle
        start_offset = int(start_offset_in_cycles * self._scale)
        if last_cycle == self._range_last_cycle:
            last_offset = self._end 
        else:
            last_offset_in_cycles = last_cycle+1 - self._range_first_cycle
            last_offset = int(last_offset_in_cycles * self._scale)-1
        return f'{self._sep}{start_offset:>{self._padlen}}{self._sep}{last_offset:>{self._padlen}}'


class NullCustomScale(object):
    def header(self):
        return ''
    def instruction(self,first_cycle, last_cycle):
        return ''

class CmTrace:
    RECORD_SIZE = 8  # (PC, cycles)
    EPILOG_SIZE = 8  # (number of instructions, total cycles)

    @property
    def instruction_count(self):
        return self._ins_cnt

    @property
    def total_cycles(self):
        return self._total_cycles

    def __init__(self, binary, func_name, setup_func_name: str = ''):
        self._binary = binary
        self._func_name = func_name
        if setup_func_name:
            self._setup_func_name = setup_func_name
        else:
            self._setup_func_name = func_name
        self._trace_path = None
        self._records_base = None
        self._ins_cnt = None
        self._total_cycles = None
        self._image = Elf(elf=self._binary, binutils_prefix='arm-none-eabi-')
        logging.debug(self._image.functions_by_name.keys())
        self._func = self._image.functions_by_name[self._func_name]
        self._func_start = self._func['start']
        self._func_last = self._func['last_ins_addr']

        self._setup_func = self._image.functions_by_name[self._setup_func_name]
        self._setup_func_start = self._setup_func['start']
        self._setup_func_last = self._setup_func['last_ins_addr']

        if self._setup_func != self._func:
            logging.debug(f'{self._setup_func_name:20}: {self._setup_func_start:#08x} to {self._setup_func_last:#08x}')

        logging.debug(f'{self._func_name:20}: {self._func_start:#08x} to {self._func_last:#08x}')

    def _get_record(self, record_index):
        with open(self._trace_path, 'rb') as f:
            f.seek(self._records_base + record_index * self.RECORD_SIZE)
            pc = read32(f)
            cy = read32(f)
            return {'pc': pc, 'cycles': cy}

    def get_records(self):
        for i in range(0, self.instruction_count):
            yield self._get_record(i)

    def dump(self,*,custom_scale=None,sep='|'):
        if custom_scale is None:
            custom_scale = NullCustomScale()
        print(f"{'index':>6}{sep}{'PC':>10}{sep}{'opcode':>6}{sep}{'cycles':>6}{sep}{'first cycle':>11}{sep}{'last cycle':>10}{custom_scale.header()}")  # noqa T201
        index = 0
        scy = 0
        for r in self.get_records():
            first_cycle = scy
            scy += r['cycles']
            last_cycle = scy - 1
            print(  # noqa T201
                f"{index:6}{sep}0x{r['pc']:08x}{sep}{self._image.addresses[r['pc']]['ins']:>6}{sep}{r['cycles']:6}{sep}{first_cycle:11}{sep}{last_cycle:10}{custom_scale.instruction(first_cycle, last_cycle)}"
            )
            index += 1
        if self.instruction_count != index:
            raise RuntimeError(f'instruction count mismatch: {self.instruction_count} vs {index}')
        if self.total_cycles != scy:
            raise RuntimeError(f'total cycles mismatch: {self.total_cycles} vs {scy}')
        print(f'{self.instruction_count} instructions, {self.total_cycles} cycles')  # noqa T201

    @staticmethod
    def from_file(trace_path):
        with open(trace_path, 'rb') as f:

            def f_read_str():
                return read_str(f)

            binary = f_read_str()
            func_name = f_read_str()
            setup_func_name = f_read_str()
            trace = CmTrace(binary, func_name, setup_func_name)
            trace._trace_path = trace_path
            trace._records_base = f.tell()
            logging.debug(f'{Utils.hexstr(f.read())}')
            f.seek(-trace.EPILOG_SIZE, os.SEEK_END)
            trace._ins_cnt = (f.tell() - trace._records_base) // trace.RECORD_SIZE
            ins_cnt = read32(f)
            trace._total_cycles = read32(f)
            if ins_cnt != trace._ins_cnt:
                raise RuntimeError(
                    f'File {trace_path} seems corrupted: inconsistent size vs number of instruction ({trace._ins_cnt} vs {ins_cnt})'
                )
            return trace

    def capture(self, device, *, out_dir=None):
        trace_path = f'{os.path.basename(self._binary)}-{self._setup_func_name}.cmtrace'
        if out_dir:
            trace_path = os.path.join(out_dir, trace_path)

        device.flush()
        device.reset_input_buffer()

        def device_write32(x: int):
            write32(device, x)

        rx_log = bytearray()

        def device_read(size: int = 1):
            nonlocal rx_log
            dat = device.read(size)
            rx_log += dat
            return dat

        def device_read32() -> int:
            return int.from_bytes(device_read(4), byteorder='little')

        device_write32(self._setup_func_start)
        hello = device_read(8)
        if hello != b'cmtrace\0':
            raise RuntimeError(f'hello = {hello} ({Utils.hexstr(hello)})')
        free_run_cycles = device_read32()
        logging.debug(f'{free_run_cycles} cycles measured in free run (includes setup and timer read)')

        with open(trace_path, 'wb') as f:

            def f_write32(x: int):
                write32(f, x)

            def f_write_str(s: str):
                write_str(f, s)

            f_write_str(self._binary)
            f_write_str(self._func_name)
            f_write_str(self._setup_func_name)

            cnt = 1
            last_pc = None
            last_cnt = 1
            ins_cnt = 0
            ins_cnt_setup = 0
            func_cycles = 0
            is_setup = True
            ra_in_setup = 0xFFFFFFFF
            if self._func == self._setup_func:
                is_setup = False

            def add_instruction():
                nonlocal ins_cnt, ins_cnt_setup
                last_pc_cycles = cnt - last_cnt
                if is_setup:
                    ins_cnt_setup += 1
                    logging.debug(
                        f"PC={last_pc:#08x}: {last_pc_cycles} {self._image.addresses[last_pc]['ins']} (setup)"
                    )
                else:
                    ins_cnt += 1
                    logging.info(f"PC={last_pc:#08x}: {last_pc_cycles} {self._image.addresses[last_pc]['ins']}")
                    f_write32(last_pc)
                    f_write32(last_pc_cycles)

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
                    if pc == self._func_start:
                        is_setup = False
                        ra_in_setup = last_pc + self._image.addresses[last_pc]['size']
                        logging.debug(f'{self._image.addresses[last_pc]}')
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
                logging.info(Utils.hexstr(rx_log))
                raise RuntimeError(f'cnt={cnt}, total_cycles={total_cycles}')
            print(f'{self._func_name}: {ins_cnt} instructions, {func_cycles} cycles')  # noqa T201
            f_write32(ins_cnt)
            f_write32(func_cycles)
        self._trace_path = trace_path
        self._total_cycles = func_cycles
        self._ins_cnt = ins_cnt
