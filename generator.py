import os, filters
from distutils.dir_util import copy_tree
from typing import Dict, List
from jinja2 import Environment, PackageLoader
from xml.etree import ElementTree

env = Environment(
    loader=PackageLoader('generator', 'templates'),
    keep_trailing_newline=True,
)

env.filters["bitflag"] = filters.bitflag
env.filters["escape_backslashes"] = filters.escape_backslashes
env.filters["hex_string"] = filters.hex_string
env.filters["enum_name"] = filters.enum_name
env.filters["field_name"] = filters.field_name
env.filters["to_basic_type"] = filters.to_basic_type

basics: List[str] = []


def write_file(filename: str, contents: str):
    dir = os.path.dirname(filename)
    if not os.path.exists(dir):
        os.makedirs(dir)
    with open(filename, 'w', encoding='utf-8') as file:
        file.write(contents)

def write_basic(element: ElementTree.Element):
    print(element.attrib['name'])
    if element.attrib.get('integral', 'false') == 'true' and (element.attrib.get('boolean', 'false') == 'false' or element.attrib['name'] == 'byte'):
        size: int = int(element.attrib.get('size', '4'))
        signed: bool = element.attrib.get('countable', 'true') == 'true'
        min_value: str = hex(not signed and -pow(2, size * 4) or 0)
        max_value: str = hex(pow(2, size * (not signed and 8 or 4)) - 1)
        write_file(
            "output/basics/%s.py" % (element.attrib['name']),
            env.get_template('basic_integral.py.jinja').render(
                basic=element, min=min_value, max=max_value, size=size)
        )
        basics.append(element.attrib['name'])


