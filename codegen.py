import logging
import time # for timing stuff
import re
import types
import os
import sys
import collections
import xml.etree.ElementTree as ET
import os, filters
from distutils.dir_util import copy_tree
from typing import Dict, List
# from jinja2 import Environment, PackageLoader
from xml.etree import ElementTree
from html import unescape

import naming_conventions as convention
from expression import Expression, Version

logging.basicConfig(level=logging.DEBUG)

# env = Environment(
#     loader=PackageLoader('__init__', 'templates'),
#     keep_trailing_newline=True,
# )
#
# env.filters["bitflag"] = filters.bitflag
# env.filters["escape_backslashes"] = filters.escape_backslashes
# env.filters["hex_string"] = filters.hex_string
# env.filters["enum_name"] = filters.enum_name
# env.filters["field_name"] = filters.field_name
# env.filters["to_basic_type"] = filters.to_basic_type

basics: List[str] = []

FIELD_TYPES = ("add", "field")
VER = "stream.version"

def write_file(filename: str, contents: str):
    file_dir = os.path.dirname(filename)
    if not os.path.exists(file_dir):
        os.makedirs(file_dir)
    with open(filename, 'w', encoding='utf-8') as file:
        file.write(contents)


class Imports:
    """Creates and writes an import block"""

    def __init__(self, parser, xml_struct):
        self.parent = parser
        self.xml_struct = xml_struct
        self.path_dict = parser.path_dict
        self.imports = []
        # import parent class
        self.add(xml_struct.attrib.get("inherit"))

        # import classes used in the fields
        for field in xml_struct:
            if field.tag in ("add", "field", "member"):
                field_type = field.attrib["type"]
                template = field.attrib.get("template")
                self.add(template)
                if field_type == "self.template":
                    self.add("typing")
                else:
                    self.add(field_type)
                # arr1 needs typing.List
                arr1 = field.attrib.get("arr1")
                if arr1:
                    self.add("typing")


    def add(self, cls_to_import):
        if cls_to_import:
            must_import, import_type = self.parent.map_type(cls_to_import)
            if must_import:
                self.imports.append(import_type)

    def write(self, stream):
        for class_import in set(self.imports):
            if class_import in self.path_dict:
                import_path = "generated." + self.path_dict[class_import].replace("\\", ".")
                stream.write(f"from {import_path} import {class_import}\n")
            else:
                stream.write(f"import {class_import}\n")
        if self.imports:
            stream.write("\n\n")


class XmlParser:
    struct_types = ("compound", "niobject", "struct")
    bitstruct_types = ("bitfield", "bitflags", "bitstruct")

    def __init__(self, format_name):
        """Set up the xml parser."""

        self.format_name = format_name
        # initialize dictionaries
        # map each supported version string to a version number
        versions = {}
        # map each supported game to a list of header version numbers
        games = {}
        # note: block versions are stored in the _games attribute of the struct class

        # elements for creating new classes
        self.class_name = None
        self.class_dict = None
        self.base_class = ()
        #
        # self.basic_classes = []
        # # these have to be read as basic classes
        # self.compound_classes = []

        # elements for versions
        self.version_string = None

        # ordered (!) list of tuples ({tokens}, (target_attribs)) for each <token>
        self.tokens = []
        self.versions = [ ([], ("versions", "until", "since")), ]

        # maps each type to its generated py file's relative path
        self.path_dict = {}
        # maps each type to its member tag type
        self.tag_dict = {}

        self.storage_types = set()

    def generate_module_paths(self, root):
        """preprocessing - generate module paths for imports relative to the output dir"""
        for child in root:
            # only check stuff that has a name - ignore version tags
            if child.tag not in ("version", "module", "token"):
                class_name = convention.name_class(child.attrib["name"])
                out_segments = ["formats", self.format_name, child.tag, ]
                if child.tag == "niobject":
                    out_segments.append(child.attrib["module"])
                out_segments.append(class_name)
                # store the final relative module path for this class
                self.path_dict[class_name] = os.path.join(*out_segments)
                self.tag_dict[class_name.lower()] = child.tag
        # print(self.path_dict)
        # source_dir = os.path.join(os.getcwd(),"source")
        # for file in os.listdir(source_dir):
        #     f, ext = os.path.splitext(file)
        #     if ext:
        #         self.path_dict[class_name] = os.path.join(source_dir, f)

        self.path_dict["BasicBitfield"] = "bitfield"
        self.path_dict["BitfieldMember"] = "bitfield"

    def load_xml(self, xml_file):
        """Loads an XML (can be filepath or open file) and does all parsing
        Goes over all children of the root node and calls the appropriate function depending on type of the child"""
        # try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        self.generate_module_paths(root)

        for child in root:
            try:
                if child.tag in self.struct_types:
                    # StructWriter(child)
                    self.read_struct(child)
                # elif child.tag in self.bitstruct_types:
                #     self.read_bitstruct(child)
                # elif child.tag == "basic":
                #     self.write_basic(child)
                # elif child.tag == "enum":
                #     self.write_enum(child)
                elif child.tag == "bitfield":
                    self.write_bitfield(child)
                # elif child.tag == "bitflags":
                #     self.write_bitflags(child)
                # elif child.tag == "module":
                #     self.read_module(child)
                # elif child.tag == "version":
                #     self.read_version(child)
                elif child.tag == "token":
                    self.read_token(child)
            except Exception as err:
                logging.error(err)
        logging.info(self.storage_types)

    # the following constructs do not create classes
    def read_token(self, token):
        """Reads an xml <token> block and stores it in the tokens list"""
        self.tokens.append(([(sub_token.attrib["token"], sub_token.attrib["string"])
                            for sub_token in token],
                            token.attrib["attrs"].split(" ")))
        
    def read_version(self, version):
        """Reads an xml <version> block and stores it in the versions list"""
        # todo [versions] this ignores the user vers!
        # versions must be in reverse order so don't append but insert at beginning
        if "id" in version.attrib:
            self.versions[0][0].insert( 0, (version.attrib["id"], version.attrib["num"]) )
        # add to supported versions
        self.version_string = version.attrib["num"]
        self.cls.versions[self.version_string] = self.cls.version_number(self.version_string)
        self.update_gamesdict(self.cls.games, version.text)
        self.version_string = None


    def clean_comment_str(self, comment_str="", indent=""):
        """Reformats an XML comment string into multi-line a python style comment block"""
        if comment_str is None:
            return ""
        if not comment_str.strip():
            return ""
        lines = [f"\n{indent}# {line.strip()}" for line in comment_str.strip().split("\n")]
        return "\n" + "".join(lines)

    def get_names(self, struct, attrs):
        # struct types can be organized in a hierarchy
        # if inherit attribute is defined, look for corresponding base block
        class_name = convention.name_class(attrs.get("name"))
        class_basename = attrs.get("inherit")
        class_debug_str = self.clean_comment_str(struct.text, indent="\t")
        if class_basename:
            # avoid turning None into 'None' if class doesn't inherit
            class_basename = convention.name_class(class_basename)
            # logging.debug(f"Struct {class_name} is based on {class_basename}")
        return class_name, class_basename, class_debug_str

    def get_out_path(self, class_name):

        # get the module path from the path of the file
        out_file = os.path.join(os.getcwd(), "generated", self.path_dict[class_name]+".py")
        out_dir = os.path.dirname(out_file)
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        return out_file

    def apply_convention(self, struct, func, params):
        for k in params:
            if struct.attrib.get(k):
                struct.attrib[k] = func(struct.attrib[k])

    def apply_conventions(self, struct):
        # struct top level
        self.apply_convention(struct, convention.name_class, ("name", "inherit"))
        # a struct's fields
        for field in struct:
            if field.tag in FIELD_TYPES:
                self.apply_convention(field, convention.name_attribute, ("name",))
                self.apply_convention(field, convention.name_class, ("type",))

        # filter comment str
        struct.text = self.clean_comment_str(struct.text, indent="")

    def get_code_from_src(self, cls_name):
        cwd = os.getcwd()
        src_dir = os.path.join(cwd, "source")
        py_name = f"{cls_name.lower()}.py"

        for root, dirs, files in os.walk(src_dir):
            for name in files:
                if self.format_name in root and py_name == name.lower():
                    src_path = os.path.join(root, name)
                    print("found source", src_path)
                    with open(src_path, "r") as f:
                        return f.read()
        return ""

    def grab_src_snippet(self, src_code, start, end=""):
        # print(src_code)
        start_content = src_code.find(start)
        if start_content > -1:
            if end:
                end_content = src_code.find(end)
                if end_content > -1:
                    snipp = src_code[start_content + len(start):end_content]
                    # print("found start + end", len(snipp), start, end)
                    return snipp
            snipp = src_code[start_content + len(start):]
            # print("found start", len(snipp), start, end)
            return snipp
        return ""

    def read_struct(self, struct):
        """Create a struct class"""
        self.replace_tokens(struct)
        self.apply_conventions(struct)
        class_name = struct.attrib.get("name")
        # grab the source code, if it exists
        src_code = self.get_code_from_src(class_name)
        # print("class_name", class_name)
        # print(src_code)
        class_basename = struct.attrib.get("inherit")
        class_debug_str = struct.text
        out_file = self.get_out_path(class_name)
        # handle imports
        imports = Imports(self, struct)

        field_unions_dict = collections.OrderedDict()
        for field in struct:
            if field.tag in FIELD_TYPES:
                field_name = field.attrib["name"]
                if field_name not in field_unions_dict:
                    field_unions_dict[field_name] = []
                else:
                    # field exists and we add to it, so we have an union and must import typing module
                    imports.add("typing")
                field_unions_dict[field_name].append(field)

        # write to python file
        with open(out_file, "w") as f:
            f.write(self.grab_src_snippet(src_code, "# START_GLOBALS", "# END_GLOBALS"))

            imports.write(f)

            inheritance = f"({class_basename})" if class_basename else ""
            f.write(f"class {class_name}{inheritance}:")
            if class_debug_str:
                f.write(class_debug_str)

            # check all fields/members in this class and write them as fields
            for field_name, union_members in field_unions_dict.items():
                field_types = []
                for field in union_members:
                    field_type = field.attrib["type"]
                    # todo - make consisten / merge with map_type()
                    if field_type == "self.template":
                        field_type = "typing.Any"
                        imports.add("typing")
                    elif field_type.lower() in ("byte", "ubyte", "short", "ushort", "int", "uint", "int64", "uint64"):
                        field_type = "int"
                    elif field_type.lower() in ("float", "hfloat"):
                        field_type = "float"
                    elif field_type.lower() in ("bool",):
                        field_type = "bool"
                    field_types.append(field_type)
                    field_default = field.attrib.get("default")
                    field_debug_str = self.clean_comment_str(field.text, indent="\t")

                    if field_debug_str.strip():
                        f.write(field_debug_str)
                field_types = set(field_types)
                if len(field_types) > 1:
                    field_types_str = f"typing.Union[{', '.join(field_types)}]"
                else:
                    field_types_str = field_type

                # write the field type
                # arrays
                if field.attrib.get("arr1"):
                    f.write(f"\n\t{field_name}: typing.List[{field_types_str}]")
                # plain
                else:
                    f.write(f"\n\t{field_name}: {field_types_str}")

                # write the field's default, if it exists
                if field_default:
                    # we have to check if the default is an enum default value, in which case it has to be a member of that enum
                    if self.tag_dict[field_type.lower()] == "enum":
                        field_default = field_type+"."+field_default
                    f.write(f" = {field_default}")

                # todo - handle several defaults? maybe save as docstring
                # load defaults for this <field>
                # for default in field:
                #     if default.tag != "default":
                #         raise AttributeError("struct children's children must be 'default' tag")

            if "def __init__" not in src_code:
                f.write(f"\n\n\tdef __init__(self, arg=None, template=None):")
                # classes that this class inherits from have to be read first
                if class_basename:
                    f.write(f"\n\t\tsuper().__init__(arg, template)")
                f.write(f"\n\t\tself.arg = arg")
                f.write(f"\n\t\tself.template = template")
                f.write(f"\n\t\tself.io_size = 0")

                for field in struct:
                    if field.tag in FIELD_TYPES:
                        field_name = field.attrib["name"]
                        field_type = field.attrib["type"]
                        field_default = field.attrib.get("default")
                        if field_type.lower() in self.tag_dict:
                            type_of_field_type = self.tag_dict[field_type.lower()]
                            # write the field's default, if it exists
                            if field_default:
                                # we have to check if the default is an enum default value, in which case it has to be a member of that enum
                                if type_of_field_type == "enum":
                                    field_default = field_type + "." + field_default
                            # no default, so guess one
                            else:
                                if type_of_field_type in ("compound", "niobject"):
                                    field_default = f"{field_type}()"
                        if not field_default:
                            field_default = 0
                        f.write(f"\n\t\tself.{field_name} = {field_default}")

            # write the load() method
            for method_type in ("read", "write"):
                # check all fields/members in this class and write them as fields
                if f"def {method_type}(" in src_code:
                    continue
                f.write(f"\n\n\tdef {method_type}(self, stream):")
                f.write(f"\n\n\t\tio_start = stream.tell()")
                last_condition = ""
                # classes that this class inherits from have to be read first
                if class_basename:
                    f.write(f"\n\t\tsuper().{method_type}(stream)")

                for field in struct:
                    if field.tag in FIELD_TYPES:
                        field_name = field.attrib["name"]
                        field_type = field.attrib["type"]

                        # parse all conditions
                        conditionals = []
                        ver1 = field.attrib.get("ver1")
                        ver2 = field.attrib.get("ver2")
                        if ver1:
                            ver1 = Version(ver1)
                        if ver2:
                            ver2 = Version(ver2)
                        vercond = field.attrib.get("vercond")
                        cond = field.attrib.get("cond")

                        if ver1 and ver2:
                            conditionals.append(f"{ver1} <= {VER} < {ver2}")
                        elif ver1:
                            conditionals.append(f"{VER} >= {ver1}")
                        elif ver2:
                            conditionals.append(f"{VER} < {ver2}")
                        if vercond:
                            vercond = Expression(vercond)
                            conditionals.append(f"{vercond}")
                        if cond:
                            cond = Expression(cond)
                            conditionals.append(f"{cond}")
                        if conditionals:
                            new_condition = f"if {' and '.join(conditionals)}:"
                            # merge subsequent fields that have the same condition
                            if last_condition != new_condition:
                                f.write(f"\n\t\t{new_condition}")
                            indent = "\n\t\t\t"
                        else:
                            indent = "\n\t\t"
                            new_condition = ""
                        last_condition = new_condition
                        template = field.attrib.get("template")
                        if template:
                            template_str = f"template={template}"
                            f.write(f"{indent}# TEMPLATE: {template_str}")
                        else:
                            template_str = ""
                        arr1 = field.attrib.get("arr1")
                        arr2 = field.attrib.get("arr2")
                        arg = field.attrib.get("arg")
                        if arg:
                            arg = Expression(arg)

                        f.write(f"{indent}{self.method_for_type(field_type, mode=method_type, attr=f'self.{field_name}', arr1=arr1, arg=arg)}")
                        # store version related stuff on stream
                        if "version" in field_name:
                            f.write(f"{indent}stream.{field_name} = self.{field_name}")
                f.write(f"\n\n\t\tself.io_size = stream.tell() - io_start")

            if "def __repr__(" not in src_code:
                f.write(f"\n\n\tdef __repr__(self):")
                f.write(f"\n\t\ts = '{class_name} [Size: '+str(self.io_size)+']'")
                for field in struct:
                    if field.tag in FIELD_TYPES:
                        field_name = field.attrib["name"]
                        f.write(f"\n\t\ts += '\\n\t* {field_name} = ' + self.{field_name}.__repr__()")
                f.write(f"\n\t\ts += '\\n'")
                f.write(f"\n\t\treturn s")

            f.write(self.grab_src_snippet(src_code, "# START_CLASS"))


    def collect_types(self, imports, struct):
        """Iterate over all fields in struct and collect type references"""
        # import classes used in the fields
        for field in struct:
            if field.tag in ("add", "field", "member"):
                field_type = convention.name_class(field.attrib["type"])
                if field_type not in imports:
                    if field_type == "self.template":
                        imports.append("typing")
                    else:
                        imports.append(field_type)

    def write_imports(self, f, imports):
        for class_import in imports:
            if class_import in self.path_dict:
                import_path = "generated."+self.path_dict[class_import].replace("\\", ".")
                f.write(f"from {import_path} import {class_import}\n")
            else:
                f.write(f"import {class_import}\n")

    def method_for_type(self, dtype: str, mode="read", attr="self.dummy", arr1=None, arg=None):
        args = ""
        if arg:
            args = f", ({arg},)"
        # template or custom type
        if "template" in dtype.lower() or self.tag_dict[dtype.lower()] != "basic":
            io_func = f"{mode}_type"
        # basic type
        else:
            io_func = f"{mode}_{dtype.lower()}"
            dtype = ""
        if not arr1:
            if mode == "read":
                return f"{attr} = stream.{io_func}({dtype}{args})"
            elif mode == "write":
                return f"stream.{io_func}({attr})"
        else:
            arr1 = Expression(arr1)
            if mode == "read":
                return f"{attr} = [stream.{io_func}({dtype}{args}) for _ in range({arr1})]"
            elif mode == "write":
                return f"for item in {attr}: stream.{io_func}(item)"

            # todo - handle array 2
            # f.write(f"{indent}self.{field_name} = [{field_type}({template_str}) for _ in range({arr1})]")
        #     f.write(f"{indent}for item in self.{field_name}:")
        #     f.write(f"{indent}\titem.{method_type}(stream)")
        # return # f.write(f"{indent}self.{field_name} = {field_type}().{method_type}(stream)")
            # raise ModuleNotFoundError(f"Storage {dtype} is not a basic type.")
        # array of basic
        # if num_bones:
        #     self.bone_data = [stream.read_type(NiSkinDataBoneData) for _ in range(num_bones)]

    def write_basic(self, element: ElementTree.Element):
        class_name = convention.name_class(element.attrib['name'])
        if element.attrib.get('integral', 'false') == 'true' and (
                element.attrib.get('boolean', 'false') == 'false' or element.attrib['name'] == 'byte'):
            size: int = int(element.attrib.get('size', '4'))
            signed: bool = element.attrib.get('countable', 'true') == 'true'
            min_value: str = hex(not signed and -pow(2, size * 4) or 0)
            max_value: str = hex(pow(2, size * (not signed and 8 or 4)) - 1)
            write_file(self.get_out_path(class_name),
                env.get_template('basic_integral.py.jinja').render(
                    basic=element, min=min_value, max=max_value, size=size)
            )
            basics.append(element.attrib['name'])

    def write_bitflags(self, element: ElementTree.Element):
        class_name = convention.name_class(element.attrib['name'])
        out_file = os.path.join(os.getcwd(), "generated", self.path_dict[class_name]+".py")
        write_file(out_file, env.get_template('bitflags.py.jinja').render(bitflags=element))

    def write_storage_io_methods(self, f, storage):
        for method_type in ("read", "write"):
            f.write(f"\n\n\tdef {method_type}(self, stream):")
            f.write(f"\n\t\t{self.method_for_type(storage, mode=method_type, attr='self._value')}")
            # f.write(f"\n")

    def map_type(self, in_type):
        l_type = in_type.lower()
        if self.tag_dict.get(l_type) != "basic":
            return True, in_type
        else:
            if "float" in l_type:
                return False, "float"
            elif l_type == "bool":
                return False, "bool"
            else:
                return False, "int"

    def write_bitfield(self, element: ElementTree.Element):
        class_name, class_basename, class_debug_str = self.get_names(element, element.attrib)

        out_file = self.get_out_path(class_name)
        storage = element.attrib["storage"]
        self.storage_types.add(storage)
        imports = ["BasicBitfield", "BitfieldMember"]
        dummy_imports = []
        self.collect_types(dummy_imports, element)
        for in_type in dummy_imports:
            must_import, in_type = self.map_type(in_type)
            if must_import:
                imports.append(in_type)
        # write to python file
        with open(out_file, "w") as f:
            self.write_imports(f, imports)

            if imports:
                f.write("\n\n")
            f.write(f"class {class_name}(BasicBitfield):")
            if class_debug_str:
                f.write(class_debug_str)

            for field in element:
                field_name = convention.name_attribute(field.attrib["name"])
                _, field_type = self.map_type(convention.name_class(field.attrib["type"]))
                f.write(f"\n\t{field_name} = BitfieldMember(pos={field.attrib['pos']}, mask={field.attrib['mask']}, return_type={field_type})")

            f.write("\n\n\tdef set_defaults(self):")
            defaults = []
            for field in element:
                field_name = convention.name_attribute(field.attrib["name"])
                field_type = convention.name_class(field.attrib["type"])
                field_default = field.attrib.get("default")
                # write the field's default, if it exists
                if field_default:
                    # we have to check if the default is an enum default value, in which case it has to be a member of that enum
                    if self.tag_dict[field_type.lower()] == "enum":
                        field_default = field_type+"."+field_default
                    defaults.append((field_name, field_default))
            if defaults:
                for field_name, field_default in defaults:
                    f.write(f"\n\t\tself.{field_name} = {field_default}")
            else:
                f.write(f"\n\t\tpass")

            self.write_storage_io_methods(f, storage)

            f.write("\n")

    def write_enum(self, element: ElementTree.Element):
        storage = element.attrib["storage"]
        self.storage_types.add(storage)
        class_name = convention.name_class(element.attrib['name'])
        out_file = os.path.join(os.getcwd(), "generated", self.path_dict[class_name]+".py")
        write_file(out_file, env.get_template('enum.py.jinja').render(enum=element))


    # the following are helper functions
    def is_generic(self, attr):
        # be backward compatible
        return (attr.get("generic") == "true") or (attr.get("istemplate") == "1")

    def update_gamesdict(self, gamesdict, ver_text):
        if ver_text:
            # update the gamesdict dictionary
            for gamestr in (g.strip() for g in ver_text.split(',')):
                if gamestr in gamesdict:
                    gamesdict[gamestr].append(self.cls.versions[self.version_string])
                else:
                    gamesdict[gamestr] = [self.cls.versions[self.version_string]]
        
    def update_class_dict(self, attrs, doc_text):
        """This initializes class_dict, sets the class name and doc text"""
        doc_text = doc_text.strip() if doc_text else ""
        self.class_name = attrs["name"]
        self.class_dict = {"__doc__": doc_text, "__module__": self.cls.__module__}

    def update_doc(self, doc, doc_text):
        if doc_text:
            doc += doc_text.strip()
            
    def replace_tokens(self, xml_struct):
        """Update xml_struct's (and all of its children's) attrib dict with content of tokens+versions list."""
        # replace versions after tokens because tokens include versions
        for tokens, target_attribs in self.tokens + self.versions:
            for target_attrib in target_attribs:
                if target_attrib in xml_struct.attrib:
                    expr_str = xml_struct.attrib[target_attrib]
                    for op_token, op_str in tokens:
                        expr_str = expr_str.replace(op_token, op_str)
                    # get rid of any remaining html escape characters
                    xml_struct.attrib[target_attrib] = unescape(expr_str)
        # additional tokens that are not specified by nif.xml
        # ("User Version", "user_version"), ("BS Header\\BS Version", "bs_header\\bs_version"), ("Version", "version")
        fixed_tokens = (("\\", "."), ("#ARG#", "arg"), ("#T#", "self.template"))
        for attrib, expr_str in xml_struct.attrib.items():
            for op_token, op_str in fixed_tokens:
                expr_str = expr_str.replace(op_token, op_str)
            xml_struct.attrib[attrib] = expr_str
        # onlyT & excludeT act as aliases for deprecated cond
        for t, pref in (("onlyT", ""), ("excludeT", "!")):
            if t in xml_struct.attrib:
                xml_struct.attrib["cond"] = pref+xml_struct.attrib[t]
                break
        for xml_child in xml_struct:
            self.replace_tokens(xml_child)

def copy_src_to_generated():
    """copies the files from the source folder to the generated folder"""
    cwd = os.getcwd()
    src_dir = os.path.join(cwd, "source")
    trg_dir = os.path.join(cwd, "generated")
    copy_tree(src_dir, trg_dir)

def generate_classes():
    logging.info("Starting class generation")
    cwd = os.getcwd()
    root_dir = os.path.join(cwd, "source\\formats")
    copy_src_to_generated()
    for format_name in os.listdir(root_dir):
        dir_path = os.path.join(root_dir, format_name)
        if os.path.isdir(dir_path):
            xml_path = os.path.join(dir_path, format_name+".xml")
            if os.path.isfile(xml_path):
                logging.info(f"Reading {format_name} format")
                xmlp = XmlParser(format_name)
                xmlp.load_xml(xml_path)


generate_classes()
#
# import source.formats.ovl
#
# print(source.formats.ovl)