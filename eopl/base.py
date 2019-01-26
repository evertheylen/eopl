
from dataclasses import dataclass, replace, field
from collections import ChainMap


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
    
    def clean_env(self):
        return replace(self, env=Environment())

    def wrap(self, value):
        return value
