"""
Utility methods
"""
import os
import pathlib
from typing import Optional, List
from inspect import getframeinfo, stack

import jinja2 as j2

PATH = pathlib.Path(__file__).parent.absolute()
VERSION_PATH = os.path.join(PATH, 'VERSION')
TEMPLATE_PATH = os.path.join(PATH, 'templates')
EXAMPLES_PATH = os.path.join(PATH, 'examples')

TEMPLATE_ENV = j2.Environment(
    loader=j2.FileSystemLoader(TEMPLATE_PATH),
    autoescape=j2.select_autoescape()
)


def get_version():
    with open(VERSION_PATH) as file:
        return file.read().replace(' ', '').replace('\n', '')


# https://stackoverflow.com/questions/24438976
class RecordCode:

    def __init__(self,
                 stack_index: int = 2,
                 clip_indent: bool = True):
        self.stack_index = stack_index
        self.clip_indent = clip_indent

        self.file_path: Optional[str] = None
        self.start_line: Optional[int] = None
        self.end_line: Optional[int] = None
        self.code_lines: List[str] = []
        self.code_string: str = ''

    def get_frameinfo(self):
        return getframeinfo(stack()[self.stack_index][0])

    def extract_code_string(self) -> None:
        with open(self.file_path) as file:
            self.code_lines = file.readlines()[self.start_line:self.end_line]

        if self.clip_indent:
            indent = self.detect_indent()
            self.code_lines = [line[indent:] for line in self.code_lines]

        self.code_string = ''.join(self.code_lines)

    def detect_indent(self) -> int:
        # https://stackoverflow.com/questions/13648813
        indents = [len(line) - len(line.lstrip(' '))
                   for line in self.code_lines
                   if len(line.strip('\n ')) != 0]
        return min(indents)

    def __enter__(self) -> 'RecordCode':
        frame_info = self.get_frameinfo()
        self.file_path = frame_info.filename
        self.start_line = frame_info.lineno

        return self

    def __exit__(self, *args) -> bool:
        frame_info = self.get_frameinfo()
        self.end_line = frame_info.lineno

        self.extract_code_string()
