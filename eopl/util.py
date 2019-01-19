
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


class NotFlat(Exception):
    def __init__(self, content, *a, **kw):
        self.content = content
        super().__init__(*a, **kw)

    def __str__(self):
        return "The set {} is not of length 1.".format(self.content)
