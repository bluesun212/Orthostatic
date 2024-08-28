from collections.abc import MutableMapping
from html.parser import HTMLParser
from itertools import chain


class PersistentDict(MutableMapping):
    def __init__(self, data=None):
        super().__init__()

        self.access_data = set()
        self.pause = False
        self.data = {}
        if data is not None:
            self.data = data

    def __len__(self):
        return len(self.data)

    def __getitem__(self, key):
        if not self.pause:
            self.access_data.add(key)
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __delitem__(self, key) -> None:
        del self.data[key]

    def __iter__(self):
        return iter(self.data)

    def start_accesses(self):
        self.access_data = set()
        self.pause = False

    def pause_accesses(self, pause):
        self.pause = pause

    def stop_accesses(self):
        return self.access_data


class MultiDict(MutableMapping):
    def __init__(self, dicts, overflow):
        self.dicts = dicts
        self.overflow = overflow

    def __setitem__(self, key, value) -> None:
        d, _, exists = self._get(key)
        if not exists:
            self.overflow[key] = value
        else:
            d[key] = value

    def __delitem__(self, key) -> None:
        d, _, exists = self._get(key)
        if not exists:
            raise KeyError(key)
        del d[key]

    def __getitem__(self, key):
        _, val, exists = self._get(key)
        if not exists:
            raise KeyError(key)
        return val

    def __len__(self) -> int:
        return sum(map(len, self.dicts))

    def __iter__(self):
        return chain.from_iterable(map(iter, self.dicts))

    def _get(self, key):
        for d in self.dicts:
            if key in d:
                return d, d[key], True

        return None, None, False


class TagParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tag, self.attrs, self.data = None, None, None

    def handle_starttag(self, tag: str, attrs) -> None:
        self.tag, self.attrs = tag, attrs

    def handle_data(self, data: str) -> None:
        self.data = data


def parse_html_tag(html):
    parser = TagParser()
    parser.feed(html)
    return parser.tag, parser.attrs, parser.data
