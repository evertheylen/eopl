
from dataclasses import dataclass, replace, field
from pprint import PrettyPrinter
from collections import ChainMap


_pretty_printer = PrettyPrinter(indent=2, width=100)


def pprint(x):
    _pretty_printer.pprint(x)


def pretty(x):
    return _pretty_printer.pformat(x)


class Environment(ChainMap):
    layer = ChainMap.new_child



class BaseExpr:
    def free_vars(self):
        for v in vars(self).values():
            yield from v.free_vars()


@dataclass
class Context:
    env: Environment = field(default_factory=Environment)
    
    def with_layer(self, layer: dict):
        return replace(self, env=self.env.layer(layer))

