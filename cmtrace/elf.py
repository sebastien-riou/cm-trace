import logging
import os
import re
import shutil
import subprocess
import tempfile


class SectionNameNotFoundError(RuntimeError):
    pass


class Elf:
    @staticmethod
    def invoke_tool(cmd):
        try:
            res = subprocess.run(cmd, capture_output=True, check=True, shell=False)  # noqa: S603
            outstr = res.stdout.decode()
            logging.debug(outstr)
            logging.debug(res.stderr.decode())
        except subprocess.CalledProcessError as e:
            nl = '\n'
            logging.debug(f'{cmd[0]} failed')
            logging.debug(f'arguments: {e.args!s}')
            logging.debug(f'stdout{nl}{e.stdout}')
            logging.debug(f'stderr{nl}{e.stderr}')
            logging.debug(f'return code: {e.returncode}')
            raise
        return outstr

    @staticmethod
    def get_tmp_file():
        file = os.path.join(tempfile.mkdtemp(), 'elf.tmp')
        return file
    
    
    def read_file_format(self):
        outstr = self.objdump(self._elf_file, '-a')
        info_line = r'\s*\S+:\s+file format\s+(\S+)'
        m = re.search(info_line, outstr)
        self._file_format = m.group(1)
        logging.debug(f'file format is "{self._file_format}"')
        parts = self._file_format.split('-')
        match parts[0]:
            case 'elf32':
                self._addr_width = 32
            case 'elf64':
                self._addr_width = 64
            case _:
                logging.warning(f'could not identify address width, file format is "{self._file_format}"')
        logging.debug(f'address width is "{self._addr_width}"')

        match parts[1]:
            case 'littlearm':
                self._byteorder = 'little'
            case 'littleriscv':
                self._byteorder = 'little'
            case 'bigarm':
                self._byteorder = 'big'
            case 'bigriscv':
                self._byteorder = 'big'
            case _:
                logging.warning(f'could not identify endianess, file format is "{self._file_format}"')
        logging.debug(f'byteorder is "{self._byteorder}"')

        return self._file_format

    def read_sections(self) -> list:
        out = []
        outstr = self.objdump(self._elf_file, '-h')
        section_info = (
            r'\d+\s+(\S+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+2\*\*(\d+)\s*\n(.*)'
        )
        for m in re.finditer(section_info, outstr):
            flags = m.group(7).strip().split(',')
            flags = [s.strip() for s in flags]
            section = {
                'name': m.group(1),
                'size': int(m.group(2), 16),
                'vma': int(m.group(3), 16),
                'lma': int(m.group(4), 16),
                'file-offset': int(m.group(5), 16),
                'align': 2 ** int(m.group(6)),
                'flags': flags,
            }
            logging.debug(section)
            out.append(section)
        self._sections = out
        return out

    def read_functions_from_symbol_table(self) -> list:
        # report a subset of what is reported with read_functions and give less details. size is not always accurate (for example _fini may appear as 0 byte)
        outstr = self.objdump(self._elf_file, '--all-headers')
        lines = outstr.splitlines()
        syms_func_regex = r'\s*([0-9a-fA-F]+)\s+([0-9a-zA-Z ]+F)\s+(\S*)\s+([0-9a-fA-F]+)\s+(.*)'
        functions = []
        line_cnt = 0
        for line in lines:
            line_cnt += 1
            # print("%03d: "%line_cnt)
            r = re.search(syms_func_regex, line)
            if r is not None:
                addr_str = r.group(1)
                attributes = r.group(2)
                section = r.group(3)
                size_str = r.group(4)
                func_name = r.group(5)
                if ' ' in func_name:
                    func_name = func_name.split(' ')[-1]
                addr = int(addr_str, 16)
                size = int(size_str, 16)
                functions.append(
                    {'name': func_name, 'start': addr, 'size': size, 'section': section, 'attributes': attributes}
                )
        return functions

    def read_functions(self) -> list:
        outstr = self.objdump(self._elf_file, '--line-numbers', '--show-all-symbols', '--disassemble', '--wide')
        lines = outstr.splitlines()
        functions = []
        addresses = {}
        aliases = {}
        func_regex = r'([0-9a-fA-F]+)\s+<(.*)>:'
        ins_regex = r'\s*([0-9a-fA-F]+)\s*:\s+([0-9a-fA-F ]+)\s+(\S*)\s*(.*)'
        line_cnt = 0
        current_func = None
        last_addr = None
        last_size = None
        new_func = False
        for line in lines:
            line_cnt += 1
            # print("%03d: "%line_cnt)
            r = re.search(func_regex, line)
            if r is not None:
                addr_str = r.group(1)
                func_name = r.group(2)
                if func_name.startswith('$'):
                    continue  # not a real function
                addr = int(addr_str, 16)
                if current_func is not None:
                    size = last_addr + last_size - functions[-1]['start']
                    if 0 == size:
                        if current_func not in aliases:
                            aliases[current_func] = []
                        aliases[current_func].append(func_name)
                        continue
                    # print("Closing func '%s'"%current_func)
                    functions[-1]['size'] = size
                    functions[-1]['last_ins_addr'] = last_addr
                    # last instruction is not necessarily an exit! functions[-1]['exits'].append(last_addr)

                func = {'name': func_name, 'start': addr, 'exits': []}
                self._functions_by_name[func_name] = func
                functions.append(func)
                current_func = func_name
                last_addr = addr
                last_size = 0
                new_func = True
                # print("Starting func '%s'"%func_name)
            elif current_func:
                line = re.sub('<.*>', '', line)
                line = line.strip()
                r = re.search(ins_regex, line)
                if r is not None:
                    # print('Parsing instruction')
                    addr_str = r.group(1)
                    code_str = r.group(2)
                    ins = r.group(3)
                    args = r.group(4).strip()
                    addr = int(addr_str, 16)
                    code = bytearray.fromhex(code_str)
                    size = len(code)
                    last_addr = addr
                    last_size = size
                    if new_func:
                        new_func = False
                        funcs = [current_func]
                        if current_func in aliases:
                            funcs += aliases[current_func]
                    else:
                        funcs = []
                    addresses[addr] = {
                        'code': code,
                        'size': size,
                        'ins': ins,
                        'args': args,
                        'is_load': False,
                        'is_store': False,
                        'src_regs': [],
                        'dst_regs': [],
                        'functions': funcs,
                    }
        self._functions = functions
        self._functions_aliases = aliases
        self._addresses = addresses
        return self._functions

    @property
    def addr_width(self):
        if self._addr_width is None:
            self.read_file_format()
        return self._addr_width

    @property
    def byteorder(self):
        if self._byteorder is None:
            self.read_file_format()
        return self._byteorder

    @property
    def file_format(self):
        if self._file_format is None:
            self.read_file_format()
        return self._file_format

    @property
    def sections(self):
        if self._sections is None:
            self.read_sections()
        return self._sections

    @property
    def functions(self):
        if self._functions is None:
            self.read_functions()
        return self._functions

    @property
    def addresses(self):
        if self._addresses is None:
            self.read_functions()
        return self._addresses

    @property
    def functions_by_name(self):
        if self._functions is None:
            self.read_functions()
        return self._functions_by_name

    @property
    def functions_aliases(self):
        if self._functions_aliases is None:
            self.read_functions()
        return self._functions_aliases

    @staticmethod
    def from_bytes(elf_as_bytes: bytes, *, binutils_prefix='riscv-none-elf-'):
        tmp = Elf.get_tmp_file()
        with open(tmp,'wb') as f:
            f.write(elf_as_bytes)
        return Elf(tmp,binutils_prefix)
    
    def __init__(self, elf:str|bytes, *, binutils_prefix='riscv-none-elf-'):
        if isinstance(elf, str):
            self._elf_file = elf
        else:
            self._elf_file = Elf.get_tmp_file()
            with open(self._elf_file,'wb') as f:
                f.write(elf)
            logging.debug(f'tmp file: {self._elf_file}')
        self._binutils_prefix = binutils_prefix
        self._objdump_path = shutil.which(binutils_prefix + 'objdump')
        self._objcopy_path = shutil.which(binutils_prefix + 'objcopy')
        self._addr_width = None
        self._byteorder = None
        self._file_format = None
        self._sections = None
        self._functions = None
        self._addresses = None
        self._functions_by_name = {}

    def objdump(self, *args) -> str:
        cmd = [self._objdump_path, *args]
        return self.invoke_tool(cmd)

    def objcopy(self, *args) -> str:
        cmd = [self._objcopy_path, *args]
        return self.invoke_tool(cmd)

    def get_section_names(self) -> list:
        names = [n['name'] for n in self.sections]
        return names

    def get_section_by_name(self, name):
        try:
            return next(filter(lambda section: section['name'] == name, self.sections))
        except StopIteration as e:
            raise SectionNameNotFoundError(f'section "{name}" not found') from e

    def get_section_by_vma(self, vma):
        return next(filter(lambda section: section['vma'] == vma, self.sections))

    def get_section_by_lma(self, lma):
        return next(filter(lambda section: section['lma'] == lma, self.sections))

    def get_section_data(self, name) -> bytes:
        names = self.get_section_names()
        if name not in names:
            raise SectionNameNotFoundError(f'section "{name}" not found')
        section = self.get_section_by_name(name)
        if 'CONTENTS' not in section['flags']:
            return bytearray(section['size'])
        tmpfile = self.get_tmp_file()
        self.objcopy(self._elf_file, '--dump-section', name + '=' + tmpfile)
        data = open(tmpfile, 'rb').read()
        os.remove(tmpfile)
        return data

    def delete_section(self, name):
        self._sections = None
        outfile = self.get_tmp_file()
        try:
            self.objcopy(self._elf_file, '--remove-section', name, outfile)
        except subprocess.CalledProcessError as e:
            names = self.get_section_names()
            if name not in names:
                raise SectionNameNotFoundError(f'section "{name}" not found') from e
            raise
        self._elf_file = outfile

    def update_section(self, name, *, data: bytes | None = None, vma: int | None = None, lma: int | None = None):
        self._sections = None

        args = [self._elf_file]
        if data:
            tmpfile = self.get_tmp_file()
            with open(tmpfile, 'wb') as f:
                f.write(data)
            outfile = self.get_tmp_file()
            args += ['--update-section', name + '=' + tmpfile, outfile]
        if vma:
            args += ['--change-section-vma', name + '=' + str(vma)]
        if lma:
            args += ['--change-section-lma', name + '=' + str(lma)]
        try:
            self.objcopy(*args)
        except subprocess.CalledProcessError as e:
            names = self.get_section_names()
            if name not in names:
                raise SectionNameNotFoundError(f'section "{name}" not found') from e
            raise
        if data:
            self._elf_file = outfile

    def save_as(self, dst_path):
        shutil.copy(self._elf_file, dst_path)
        self._elf_file = dst_path
