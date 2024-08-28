from __future__ import annotations
from typing import Dict, List, Set, Optional, Any, Callable
from collections import defaultdict
import logging

from pathlib import Path
import os
import shutil

from jinja2 import Environment, Template, FileSystemLoader
from markdown import Markdown


CMD_START = "%"
OUTPUT_EXT = ".html"
OST_EXT = ".ost"
LOGGER = logging.getLogger("ost")

# TODOS: (un)orthodox static website builder
# Conditional rendering: Only render if return value of function changes
#   ex: given persistent['pages'], filter all whose tag is 'math'
# Persistent variables should replace global variables
# OST file trees
# Robust error handling

# Config file should have extra data parameter
# create index.html
# importing stuff from other OST templates?
# ?? Modules should have cleaner syntax (own command)


class OSTFile:
    LINE_CMDS = ['init', 'template', 'markdown']

    def __init__(self, fpath: Path):
        self.extension_name: Optional[str] = None

        # Initialize read data
        line_data = {}
        for line_type in self.LINE_CMDS:
            line_data[line_type] = []

        # Read .ost file line-by-line
        LOGGER.debug("Reading %s", fpath)
        with open(fpath) as f:
            mode = 'template'

            # TODO: re-implement with regex
            for line in f.readlines():
                # if line starts with CMD_START, extract rest of line as command and args
                if line.strip().startswith(CMD_START):
                    cmd_ind = line.index(CMD_START) + len(CMD_START)
                    cmd_args = line[cmd_ind:].strip().split()

                    # Change command mode if valid
                    if cmd_args:
                        cmd = cmd_args[0].lower()
                        if cmd in self.LINE_CMDS:
                            mode = cmd
                        elif cmd == 'extend' and len(cmd_args) > 1:
                            if self.extension_name is not None:
                                raise ValueError("You may only have one extension per file")
                            self.extension_name = cmd_args[1]
                else:
                    # Add line to correct list depending on mode
                    line_data[mode].append(line)

        # Recombine lines
        self.lines: Dict[str, str] = {}
        for line_type, line_data in line_data.items():
            self.lines[line_type] = ''.join(line_data).strip()

    def get_data(self, choice, default=None):
        return self.lines[choice] if self.lines[choice] else default


class OST:
    def __init__(self, renderer: Renderer, rel_path: Path):
        self.renderer = renderer
        self._rel_path = rel_path
        self.path = rel_path
        self.file: OSTFile = OSTFile(self.get_src_path())

        # Other fields
        self.extension: Optional[OST] = None
        self.markdown: Optional[str] = None
        self.template: Optional[Template] = None
        self._post_process_func: Optional[Callable] = None
        self.data: Dict[str, Any] = {}

    def compile(self):
        LOGGER.debug("Compiling %s", self.get_id())

        # Copy extension's data
        if self.file.extension_name:
            self.extension = self.renderer.templates.get_template(self.file.extension_name)
            self.data.update(self.extension.data)
        self.data['persistent'] = self.renderer.global_data
        self.data['this'] = self

        # Fetch file data
        template_data = self.file.get_data('template', '')
        markdown_data = self.file.get_data('markdown')
        init_data = self.file.get_data('init')

        # Add extension line to template data if applicable
        if self.extension and self.extension.template is not None:
            template_name = self.extension.get_id()
            extends_statement = f"{{% extends this.renderer.templates.template_obj['{template_name}'] %}}\n"
            template_data = (extends_statement + template_data).strip()

        # Handle markdown, init, and template data
        if markdown_data:
            self.markdown = self.renderer.markdown.reset().convert(markdown_data)

        if init_data:
            exec(init_data, self.data)

        if template_data:
            self.template = self.renderer.environment.from_string(template_data)

    def run_post_process(self, output, module):
        # Run extension's post-processing code, then this one's
        new_output = output

        if self.extension:
            new_output = self.extension.run_post_process(new_output, module)

        if self._post_process_func:
            temp_output = self._post_process_func(new_output, module)
            if temp_output is not None:
                new_output = temp_output

        return new_output

    def render(self):
        LOGGER.debug("Rendering %s", self.get_id())

        # Render template, then run post-processing code
        output, module = None, None
        if self.template:
            module = self.template.make_module(self.data)
            output = str(module)
        output = self.run_post_process(output, module)

        # Output to file
        dpath = self.get_dst_path()
        os.makedirs(dpath.parent, exist_ok=True)
        with open(dpath, 'w', encoding='utf-8') as f:
            f.write(output)

    def attach_hook(self, hook, func):
        if callable(func):
            hook = hook.lower()
            if hook == 'post_process':
                self._post_process_func = func
            else:
                self.renderer.attach_hook(hook, func)

    def extends(self, template):
        # Returns whether this OST file or one if its extensions is the given template
        if self.extension:
            if self.extension.get_id() == template:
                return True
            else:
                return self.extension.extends(template)

        return False

    # Path related methods
    def get_src_path(self):
        return (self.renderer.config.src_path / self.path).with_suffix(OST_EXT)

    def get_dst_path(self):
        return (self.renderer.config.dst_path / self.path).with_suffix(OUTPUT_EXT)

    def get_url(self):
        return str(self.path.with_suffix(OUTPUT_EXT))

    def get_id(self):
        return str(self._rel_path)


class TemplateOST(OST):
    def get_src_path(self):
        return (self.renderer.config.template_path / self.path).with_suffix(OST_EXT)


class TemplateCollection:
    def __init__(self, template_dir: Path, renderer: Renderer):
        self.template_dir = template_dir
        self.renderer = renderer

        self.templates: Dict[str, OST] = {}
        self.template_obj: Dict[str, Template] = {}
        self._importing: Set[str] = set()

    def load_templates(self):
        # Reset fields
        self.templates = {}
        self.template_obj = {}
        self._importing = set()

        # Walk through and import template directory and subdirectory OST files
        LOGGER.info("Loading templates")
        for (dir_pname, _, fnames) in os.walk(self.template_dir):
            dir_rel = Path(dir_pname).relative_to(self.template_dir)
            for fn in fnames:
                fpath = Path(fn)
                if fpath.suffix == OST_EXT:
                    self._import_template((dir_rel / Path(fn).stem).as_posix())

    def _import_template(self, name):
        # Don't re-import
        if name in self.templates.keys():
            return

        # Watch for circular imports
        if name in self._importing:
            raise ValueError("Circular import detected")
        self._importing.add(name)

        # Import template's imports, then compile template
        ost = TemplateOST(self.renderer, Path(name))
        if ost.file.extension_name:
            self._import_template(ost.file.extension_name)
        ost.compile()

        if ost.template:
            self.template_obj[name] = ost.template

        # Finished, add to template fields
        self._importing.remove(name)
        self.templates[name] = ost

    def get_template(self, name: str) -> OST:
        if name not in self.templates:
            raise ValueError("Template doesn't exist")
        return self.templates[name]


class Config:
    def __init__(self, **kwargs):
        self.base_path: Optional[Path] = None
        if 'base_path' in kwargs:
            self.base_path = Path(kwargs['base_path'])

        self.src_path = Path(kwargs.get('src_path', 'src/'))
        self.dst_path = Path(kwargs.get('dst_path', 'dst/'))
        self.template_path = Path(kwargs.get('src_path', 'templates/'))
        self.markdown_extensions: Optional[List[str]] = kwargs.get('markdown_extensions', None)
        self.markdown_config: Optional[Dict[str, Any]] = kwargs.get('markdown_config', None)
        self.extra_data: Optional[Dict[str, Any]] = kwargs.get('extra_data', None)

    def validate(self):
        if self.base_path:
            self.src_path = self.base_path / self.src_path
            self.dst_path = self.base_path / self.dst_path
            self.template_path = self.base_path / self.template_path

        if not (self.src_path.exists() and self.dst_path.exists() and self.template_path.exists()):
            raise FileNotFoundError("Source, destination, or template path does not exist")


class Renderer:
    def __init__(self, config: Config):
        self.config = config
        self.config.validate()

        # Set up
        LOGGER.debug("Initializing Jinja and Markdown objects")
        self.environment = Environment(loader=FileSystemLoader(str(self.config.template_path)))
        self.markdown = Markdown(extensions=self.config.markdown_extensions,
                                 extension_configs=self.config.markdown_config)
        self.templates = TemplateCollection(self.config.template_path, self)
        self.handlers: Dict[str, Callable] = {OST_EXT: self._render_ost}
        self.global_data: Dict[str, Any] = dict()
        self.compiled: List[OST] = []
        self.hooks = defaultdict(list)

    def _render_static(self, rel_path):
        # Create necessary folders and copy file over as-is
        os.makedirs((self.config.dst_path / rel_path).parent, exist_ok=True)
        shutil.copy(self.config.src_path / rel_path, self.config.dst_path / rel_path)

    def _render_ost(self, rel_path):
        # Create and compile OST file
        ost = OST(self, rel_path.with_suffix(''))
        ost.compile()
        self.compiled.append(ost)

    def attach_hook(self, hook, func):
        self.hooks[hook].append(func)

    def _trigger_hooks(self, hook):
        for func in self.hooks[hook]:
            func()

    def render(self):
        self.global_data = dict()
        self.compiled = []
        self.hooks = defaultdict(list)
        self.templates.load_templates()

        # Walk source directories
        LOGGER.info("Compiling OST files")
        for (dir_pname, dnames, fnames) in os.walk(self.config.src_path):
            dir_rel = Path(dir_pname).relative_to(self.config.src_path)

            # Handle each file depending on its extension
            # this allows future users to use custom extensions for various purposes
            for fn in fnames:
                rel_path = dir_rel / fn
                ext = rel_path.suffix.lower()

                if ext in self.handlers:
                    self.handlers[ext](rel_path)
                else:
                    self._render_static(rel_path)

        # Now sort OSTs according to priority and render out
        LOGGER.info("Rendering OST files")
        self._trigger_hooks('pre_render')
        for t in self.compiled:
            t.render()

        self._trigger_hooks('post_render')
        LOGGER.info("Finished")
