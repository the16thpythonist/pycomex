import os
import sys
import pathlib
import logging

import jinja2 as j2

PATH = pathlib.Path(__file__).parent.absolute()
TEMPLATE_PATH = os.path.join(PATH, 'templates')
TEMPLATE_ENV = j2.Environment(
    loader=j2.FileSystemLoader(TEMPLATE_PATH)
)
ASSETS_PATH = os.path.join(PATH, 'assets')
ARTIFACTS_PATH = os.path.join(PATH, 'artifacts')

DO_LOGGING = True
LOG = logging.Logger('test')
if DO_LOGGING:
    LOG.addHandler(logging.StreamHandler(sys.stdout))
else:
    LOG.addHandler(logging.NullHandler())


NULL_LOGGER = logging.Logger('NULL')
NULL_LOGGER.addHandler(logging.NullHandler())


def write_template(path: str,
                   template: j2.Template,
                   kwargs: dict
                   ) -> None:
    with open(path, mode='w') as file:
        content = template.render(**kwargs)
        file.write(content)
