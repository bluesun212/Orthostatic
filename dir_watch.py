import threading
import os
import time


class DirWatcher:
    def __init__(self, dirs, callback):
        self.dirs = dirs
        self.running = True
        self.callback = callback
        self.last_update = 0
        self.event = threading.Event()

        t = threading.Thread(target=self._run)
        t.start()

    def _check(self):
        for base_dir in self.dirs:
            for cur_dir, _, cur_files in os.walk(base_dir):
                for cur_file in cur_files:
                    file_path = cur_dir + '/' + cur_file
                    mod_time = os.path.getmtime(file_path)
                    if mod_time > self.last_update:
                        self.last_update = time.time()
                        return True

        return False

    def stop(self):
        self.running = False
        self.event.set()

    def _run(self):
        while self.running:
            if self._check():
                self.callback()

            self.event.wait(0.5)
