import os
import pathlib

import jinja2 as j2

PATH = pathlib.Path(__file__).parent.absolute()
TEMPLATE_PATH = os.path.join(PATH, 'templates')
TEMPLATE_ENV = j2.Environment(
    loader=j2.FileSystemLoader(TEMPLATE_PATH)
)


def write_template(path: str,
                   template: j2.Template,
                   kwargs: dict
                   ) -> None:
    with open(path, mode='w') as file:
        content = template.render(**kwargs)
        file.write(content)
