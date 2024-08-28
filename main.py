from pathlib import Path
import logging
import time
import sys

from ost import Renderer, Config
from server import Server
from dir_watch import DirWatcher


# CLI options
# -c --config-file
# -s --source
# -d --destination
# -t --template
# -h --help
# --serve

if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    LOGGER = logging.getLogger("ost")

    # Set up Renderer
    cfg = Config()
    cfg.base_path = Path("/Users/Jared/web/")
    cfg.markdown_extensions = ['tables', 'markdown_katex.extension:KatexExtension']
    katex_opts = {'insert_fonts_css': False, 'no_inline_svg': False, 'format': 'html'}
    cfg.markdown_config = {cfg.markdown_extensions[1]: katex_opts}
    renderer = Renderer(cfg)

    # Start the server and directory watcher
    dw = DirWatcher([cfg.src_path, cfg.template_path], renderer.render)
    ser = Server(8000, str(cfg.dst_path))

    # Wait forever until exit or ctrl+c is received
    try:
        while True:
            inp = input()
            if inp.lower() == 'exit':
                break

            time.sleep(0.1)
    except KeyboardInterrupt:
        pass

    # Kill threads
    dw.stop()
    ser.stop()
