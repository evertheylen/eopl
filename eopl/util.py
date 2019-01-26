
from pprint import PrettyPrinter
from collections import defaultdict


class multimap(defaultdict):
    def __init__(self, *a, **kw):
        super().__init__(set, *a, **kw)
    
    @classmethod
    def from_pairs(cls, it):
        dct = cls()
        for k, v in it:
            dct[k].add(v)
        return dct
    
    def flat_items(self):
        for k, values in self.items():
            for v in values:
                yield k, v
                
    def flat_values(self):
        for values in self.values():
            for v in values:
                yield v
    
    def flat_len(self):
        return sum(map(len, self.values()))

    def flatten(self):
        d = {}
        for k, v in self.items():
            if len(v) != 1:
                raise NotFlat(v)
            d[k] = v.pop()
        return d


def lazyprop(fn):
    attr_name = '_lazy_' + fn.__name__
    @property
    def _lazyprop(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, fn(self))
        return getattr(self, attr_name)
    return _lazyprop
    

_pretty_printer = PrettyPrinter(indent=2, width=100)


def pprint(x):
    _pretty_printer.pprint(x)


def pretty(x):
    return _pretty_printer.pformat(x)


