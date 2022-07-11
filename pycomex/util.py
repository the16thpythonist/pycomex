import os
import pathlib

import jinja2 as j2

PATH = pathlib.Path(__file__).parent.absolute()
VERSION_PATH = os.path.join(PATH, "VERSION")

TEMPLATE_ENV = j2.Environment(
    loader=j2.PackageLoader('pycomex'),
    autoescape=j2.select_autoescape()
)


def get_version():
    with open(VERSION_PATH) as file:
        return file.read().replace(" ", "").replace("\n", "")
