from pathlib import Path
from typing import List
import os.path
# import hashlib


class Resource:
    _BUF_SIZE = 1024 * 64

    def __init__(self, path: Path):
        self.path = path
        self.last_modified = -1
        # self.file_hash = -1
        self.file_size = -1
        self.dependencies: List[Resource] = []
        self.dependents: List[Resource] = []

    def _get_file_info(self):
        return os.path.getsize(self.path), os.path.getmtime(self.path)

    # def _hash_file(self):
    #     md5 = hashlib.md5()
    #     with open(self.path, 'rb') as f:
    #         while True:
    #             d = f.read(self._BUF_SIZE)
    #             if not d:
    #                 break
    #             md5.update(d)
    #
    #         return md5.hexdigest()

    def needs_update(self):
        size, lm = self._get_file_info()
        return lm != self.last_modified or size != self.file_size

    def _update(self):
        pass

    def update(self):
        self._update()

        changed = False
        size, lm = self._get_file_info()
        if lm != self.last_modified or size != self.file_size:
            changed = True
        self.last_modified = lm
        self.file_size = size

        return changed

    def is_dependency(self, other):
        if other in self.dependencies:
            return True
        else:
            for d in self.dependencies:
                if d.is_dependency(other):
                    return True

        return False

    def __lt__(self, other):
        return self.is_dependency(other)


class FileTree:
    def __init__(self):
        self.resources: List[Resource] = []
        self.dirty: List[Resource] = []

    def check_resources(self):
        self.dirty = list(filter(Resource.needs_update, self.resources))

    def update(self):
        # Sort dirty files so dependencies update first
        dirty = sorted(self.dirty)

        for r in dirty:
            if r.needs_update():
                self._do_update(r)

        self.dirty = []

    def _do_update(self, r: Resource):
        if r.update():
            for r2 in r.dependents:
                self._do_update(r2)
