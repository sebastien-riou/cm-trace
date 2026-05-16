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

def write_blob(dst, blob: bytes):
    write32(dst, len(blob))
    logging.debug(f'write {len(blob)} bytes binary blob')
    dst.write(blob)


def read_blob(src) -> bytes:
    size = read32(src)
    logging.debug(f'read {size} bytes binary blob')
    return src.read(size)


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
    
    @property
    def executed_funcs(self):
        if self._executed_funcs is None:
            self._analyze_call_stack()
        return self._executed_funcs

    @property
    def call_stack(self):
        if self._call_stack is None:
            self._analyze_call_stack()
        return self._call_stack
    
    @property
    def records(self):
        if self._records is None:
            self._get_records()
        return self._records

    def get_executed_function(self, name: str):
        return [x for x in self.executed_funcs if x['name'] == name][0]

    def __init__(self, elf:str|bytes, func_name, setup_func_name: str = ''):
        self._image = Elf(elf=elf, binutils_prefix='arm-none-eabi-')
        logging.debug(self._image.functions_by_name.keys())
        self._binary = self._image._elf_file
        self._func_name = func_name
        if setup_func_name:
            self._setup_func_name = setup_func_name
        else:
            self._setup_func_name = func_name
        self._trace_path = None
        self._records_base = None
        self._ins_cnt = None
        self._total_cycles = None
        self._func = self._image.functions_by_name[self._func_name]
        self._func_start = self._func['start']
        self._func_last = self._func['last_ins_addr']

        self._setup_func = self._image.functions_by_name[self._setup_func_name]
        self._setup_func_start = self._setup_func['start']
        self._setup_func_last = self._setup_func['last_ins_addr']

        self._executed_funcs = None
        self._call_stack = None
        self._records = None

        if self._setup_func != self._func:
            logging.debug(f'{self._setup_func_name:20}: {self._setup_func_start:#08x} to {self._setup_func_last:#08x}')

        logging.debug(f'{self._func_name:20}: {self._func_start:#08x} to {self._func_last:#08x}')

    def _get_record(self, record_index):
        with open(self._trace_path, 'rb') as f:
            f.seek(self._records_base + record_index * self.RECORD_SIZE)
            pc = read32(f)
            cy = read32(f)
            return {'pc': pc, 'cycles': cy}

    #def get_records(self):
    #    for i in range(0, self.instruction_count):
    #        yield self._get_record(i)

    def _get_records(self):
        self._records = []
        for i in range(0, self.instruction_count):
            self._records.append(self._get_record(i))

    def _analyze_call_stack(self):
        functions = []
        call_stack = [] # live call stack
        def is_in_call_stack(func) -> int|None:
            for i in range(len(call_stack)):
                cs_record = call_stack[i]
                if func == cs_record['func']:
                    return i
            return None
        self._call_stack = [] # represent the whole history of the call stack
        previous_r = None
        scy = 0
        
        for index in range(len(self.records)):
            r = self.records[index]
            logging.debug(f'{r}')
            logging.debug(f'{self._image.addresses[r['pc']]}')
            pc_functions = self._image.addresses[r['pc']]['functions']
            if len(pc_functions) == 0:
                raise RuntimeError(f'Reached address {r['pc']:#x} which is not associated with any function')
            func_name = pc_functions[0] # in case of multiple functions sharing the same address, we take the first one
            func = self._image.functions_by_name[func_name]
            if len(call_stack) == 0 or func != call_stack[-1]['func']:
                if func not in functions:
                    functions.append(func)
                    logging.debug(f'add function {func}')
                    func['calls'] = [] # list of cycle count for each call
                    func['total_cycles'] = 0
                cs_level = is_in_call_stack(func)
                if cs_level is None: # new function call, push to stack
                    logging.debug('function call')
                    if previous_r:
                        ra = previous_r['pc'] + self._image.addresses[previous_r['pc']]['size']
                        caller=previous_r['pc']
                    else:
                        ra = -1 # ensure we never match this address
                        caller = -1
                    call_index = len(func['calls'])
                    call_stack.append({'func':func,'call_idx':call_index,'return_addr':ra})
                    func['calls'].append({'cycles':0,'caller':caller,'first_index':index})
                    event = 'call'
                else:
                    logging.debug('function return')
                    ra = call_stack[cs_level+1]['return_addr']
                    if r['pc'] != ra:
                        logging.warning(f"pc={r['pc']}, ra={ra}")
                    for i in range(cs_level+1,len(call_stack)):
                        f = call_stack[i]['func']
                        f['calls'][call_stack[i]['call_idx']]['last_index']= index-1 
                    del call_stack[cs_level+1:]
                    call_index = call_stack[-1]['call_idx']
                    event = 'return'
                self._call_stack.append({'level':len(call_stack), 'func':func, 'call_index':call_index, 'event':event, 'cycle':scy})
                r['call_stack_event'] = self._call_stack[-1]
            func['calls'][call_stack[-1]['call_idx']]['cycles'] += r['cycles']
            func['total_cycles'] += r['cycles']
            previous_r = r
            scy += r['cycles']
        logging.debug(f'functions: {functions}')
        self._executed_funcs = functions
    
    def dump(self,*,custom_scale=None,sep='|',function=None, deep=True, first_cycle=None, last_cycle=None, first_ins=None, last_ins=None):
        if custom_scale is None:
            custom_scale = NullCustomScale()
        print(f"{'index':>6}{sep}{'PC':>10}{sep}{'opcode':>7}{sep}{'cycles':>6}{sep}{'first cycle':>11}{sep}{'last cycle':>10}{custom_scale.header()}{sep}{'functions':>30}{sep}{'event'}")  # noqa T201
        scy = 0
        self._analyze_call_stack()
        printed = True
        print_it = True
        target_function = False
        if function and deep:
            call_index = 0
            target_function = self.get_executed_function(function)
            function = None
            first_ins = target_function['calls'][call_index]['first_index']
            last_ins = target_function['calls'][call_index]['last_index']
        has_start_trigger = first_cycle is not None or first_ins is not None
        if has_start_trigger:
            printed=False
            print_it=False
        printed_scy = 0
        printed_ins = 0
        index = 0
        for r in self.records:
            ins_first_cycle = scy
            scy += r['cycles']
            ins_last_cycle = scy - 1
            address = self._image.addresses[r['pc']]
            ins = address['ins']
            functions = ''
            if 'functions' in address:
                functions = address['functions']
                evt = ''
            if 'call_stack_event' in r:
                evt = f"{r['call_stack_event']['event']}, call_index={r['call_stack_event']['call_index']}, level={r['call_stack_event']['level']}"
            if not has_start_trigger:
                print_it = True
            else:
                if first_cycle is not None and first_cycle >= ins_first_cycle and first_cycle <= ins_last_cycle:
                    print_it=True
                if first_ins is not None and first_ins == index:
                    print_it=True
            if function is not None:
                if not function in functions:
                    print_it = False
            if print_it:
                print(  # noqa T201
                    f"{index:6}{sep}0x{r['pc']:08x}{sep}{ins:>7}{sep}{r['cycles']:6}{sep}{ins_first_cycle:11}{sep}{ins_last_cycle:10}{custom_scale.instruction(ins_first_cycle, ins_last_cycle)}{sep}{functions}{sep}{evt}"
                )
                printed_scy += r['cycles']
                printed_ins += 1
                printed = True
            else:
                if printed:
                    print('...')
                printed = False
            if last_cycle is not None:
                if last_cycle >= ins_first_cycle and last_cycle <= ins_last_cycle:
                    print_it=False
            if last_ins is not None:
                if last_ins == index:
                    print_it=False
                    if target_function:
                        call_index += 1
                        if call_index < len(target_function['calls']):
                            first_ins = target_function['calls'][call_index]['first_index']
                            last_ins = target_function['calls'][call_index]['last_index']
            index += 1
        if self.instruction_count != index:
            raise RuntimeError(f'instruction count mismatch: {self.instruction_count} vs {index}')
        if self.total_cycles != scy:
            raise RuntimeError(f'total cycles mismatch: {self.total_cycles} vs {scy}')
        if printed_scy != self.total_cycles or printed_ins != self.instruction_count:
            print(f'Dump stats: {printed_ins} instructions, {printed_scy} cycles')  # noqa T201
        print(f'Total stats: {self.instruction_count} instructions, {self.total_cycles} cycles')  # noqa T201

    def breakdown(self,*,sep='|'):
        functions = self.executed_funcs
        logging.debug(f'functions: {functions}')
        functions.sort(key=lambda f: f['total_cycles'], reverse=True)
        func_name_len = max(len(f['name']) for f in functions)
        print(f"{'function':>{func_name_len}}{sep}{'calls':>6}{sep}{'%':>6}{sep}{'total cycles':>12}{sep}{'min cycles':>10}{sep}{'max cycles':>10}{sep}{'CT by call site':>15}{sep}{'indexes if not CT':>17}")  # noqa T201
        for func in functions:
            callers = [d['caller'] for d in func['calls']]
            caller_cycles = []
            min_cycles = 1 << 64
            max_cycles = 0
            ct_for_each_caller = 'True'
            for caller in callers:
                cycles = [d['cycles'] for d in func['calls'] if d['caller'] == caller]
                caller_min_cycles = min(cycles)
                caller_max_cycles = max(cycles)
                if caller_min_cycles != caller_max_cycles:
                    ct_for_each_caller = 'False'
                caller_cycles.append({'min':caller_min_cycles, 'max':caller_max_cycles})
                min_cycles = min(min_cycles,caller_min_cycles)
                max_cycles = max(max_cycles,caller_max_cycles)
            def find(lst, key, value):
                for i, dic in enumerate(lst):
                    if dic[key] == value:
                        return i
                return None
            min_cycles_idx = find(func['calls'],'cycles',min_cycles)
            max_cycles_idx = find(func['calls'],'cycles',max_cycles)
            if min_cycles == max_cycles:
                not_ct = ''            
            else:
                not_ct = f'min: {min_cycles_idx}, max: {max_cycles_idx}'
            print(  # noqa T201
                f"{func['name']:>{func_name_len}}{sep}{len(func['calls']):6}{sep}{func['total_cycles']*100/self.total_cycles:6.2f}{sep}{func['total_cycles']:>12}{sep}{min_cycles:>10}{sep}{max_cycles:>10}{sep}{ct_for_each_caller:>15}{sep}{not_ct:>17}"
            )


    @staticmethod
    def from_file(trace_path):
        with open(trace_path, 'rb') as f:

            def f_read_str():
                return read_str(f)

            binary = f_read_str()
            logging.info(f'Original FW path: {binary}')
            binary_as_bytes = read_blob(f)
            func_name = f_read_str()
            setup_func_name = f_read_str()
            trace = CmTrace(binary_as_bytes, func_name, setup_func_name)
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
            binary_blob = open(self._binary,'rb').read()
            write_blob(f,binary_blob)
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
                        f"PC=0x{last_pc:08x}: {last_pc_cycles} {self._image.addresses[last_pc]['ins']} (setup)"
                    )
                else:
                    ins_cnt += 1
                    logging.info(f"PC=0x{last_pc:08x}: {last_pc_cycles} {self._image.addresses[last_pc]['ins']}")
                    f_write32(last_pc)
                    f_write32(last_pc_cycles)

            while True:
                r = device_read(1)[0]
                logging.debug(f'cnt={cnt}, r=0x{r:02x}')
                match r:
                    case 0xFF:
                        logging.debug('Received 0xFF, exit')
                        device_read(3)
                        break
                    case 0xFE:
                        cy = int.from_bytes(device_read(3),byteorder='little')
                        if cy == 0xFFFFFF:
                            logging.debug('Received 0xFFFFFF, exit')
                            break
                        if cy != cnt:
                            raise RuntimeError(f'cnt={cnt}, cy={cy} (0x{cy:08x})\n{Utils.hexstr(rx_log)}')
                        pc = device_read32()
                    case _:
                        cy = cnt
                        pc = last_pc + r - 0x40
                logging.debug(f'PC=0x{pc:08x}, cycle {cy}')
                if last_pc and last_pc != pc:
                    add_instruction()
                    if pc == self._func_start:
                        is_setup = False
                        ra_in_setup = last_pc + self._image.addresses[last_pc]['size']
                        logging.debug(f'{self._image.addresses[last_pc]}')
                        logging.debug(f'ra_in_setup=0x{ra_in_setup:08x}')
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
