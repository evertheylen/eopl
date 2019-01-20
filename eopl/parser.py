
from collections import defaultdict
from dataclasses import dataclass, field, make_dataclass, MISSING
from typing import Callable, Any

from parglare import Parser, Grammar
from parglare.grammar import Production, ProductionRHS, Terminal, NonTerminal, GrammarSymbol, \
    RegExRecognizer, StringRecognizer, \
    ASSOC_NONE, ASSOC_LEFT, ASSOC_RIGHT, \
    LAYOUT, LAYOUT_ITEM, WS, EMPTY

from eopl.util import multimap

__all__ = ('Field', 'skip', 'generates', 'replaces', 'Number', 'Boolean', 'String', 'Language')


# Declare Grammar
# ===============================================


Action = Callable[[Any, list], Any]


@dataclass
class AbstractProduction:
    head: type
    body: list  # should only contain classes (to be translated)
    action: Action = None
    priority: int = 100
    assoc: str = 'none'
    
    def __post_init__(self):
        assert self.assoc in ['left', 'right', 'none']
    
    def to_parglare(self, get_symbol):
        head = get_symbol(self.head)
        body = ProductionRHS([get_symbol(s) for s in self.body])
        assoc = {'none': ASSOC_NONE, 'left': ASSOC_LEFT, 'right': ASSOC_RIGHT}[self.assoc]
        return Production(symbol=head, rhs=body, assoc=assoc, prior=self.priority)


@dataclass(frozen=True)
class Field:
    name: str
    type: type
    default: Any = None
    
    def make_dc_field(self):
        return (self.name, self.type, field(default=(MISSING if self.default is None else self.default)))


def add_tags(cls):
    if not hasattr(cls, '_productions'):
        cls._productions = []
        cls._fields = None


def skip(*symbols, **kwargs):
    def f(cls):
        add_tags(cls)
        if symbols.count(None) != 1:
            raise Exception("@skip needs exactly one mention of 'None'")
        index = symbols.index(None)
        cls._productions.append(AbstractProduction(
            head=cls,
            body=[(cls if s is None else s) for s in symbols],
            action=lambda _, nodes, _index=index: nodes[_index],
            **kwargs))
        return cls
    return f


def generates(*symbols, **kwargs):
    def f(cls):
        add_tags(cls)
        fields = {}
        field_index = {}
        for i, s in enumerate(symbols):
            if isinstance(s, Field):
                fields[s.name] = s
                field_index[s.name] = i
        if cls._fields is None:
            cls._fields = fields
            orig_cls = cls
            cls = make_dataclass(cls.__name__, 
                                 [f.make_dc_field() for f in fields.values()],
                                 bases=(cls,))
            cls._orig_type = orig_cls
            
        elif fields.keys() != cls._fields.keys():
            # TODO check defaults
            raise Exception("Fields on class differ!")
        
        def action(_, nodes, cls=cls, field_index=field_index):
            return cls(**{name: nodes[i] for name, i in field_index.items()})
        
        raw_symbols = [(s.type if isinstance(s, Field) else s) for s in symbols]
        cls._productions.append(AbstractProduction(cls, raw_symbols, action, **kwargs))
        return cls
    return f


def replaces(from_cls, **kwargs):
    def f(cls):
        add_tags(cls)
        cls._productions.append(AbstractProduction(from_cls, [cls], action=lambda _, nodes: nodes[0], **kwargs))
        return cls
    return f



# Grammar extra's
# ===============================================

_default_actions = {
    'Number': lambda _, nodes: int(nodes[0]),
    'Boolean': lambda _, nodes: nodes[0] == 'true',
    'String': lambda _, nodes: nodes[0][1:-1],
}

Number = Terminal('Number', RegExRecognizer(r"\d+"))
Boolean = Terminal('Boolean', RegExRecognizer(r"(true|false)"))
String = Terminal('String', RegExRecognizer(r'".*"'))

_comment = Terminal('_comment', RegExRecognizer(r"%.*\n"))

_layout_prods = [
    Production(LAYOUT, ProductionRHS([LAYOUT_ITEM])),
    Production(LAYOUT, ProductionRHS([LAYOUT, LAYOUT_ITEM])),
    Production(LAYOUT_ITEM, ProductionRHS([WS])),
    Production(LAYOUT_ITEM, ProductionRHS([_comment])),
    Production(LAYOUT_ITEM, ProductionRHS([EMPTY])),
]

_default_symbols = [Number, Boolean, String, _comment]



# Build the parglare grammar
# =========================================================


class Language:
    def __init__(self, start, *types):
        self.start = start
        self.types = list(types)
        if start not in self.types:
            self.types.append(start)
            
        self.grammar, self.actions = self.make_grammar(start, self.types)
        self.parser = Parser(self.grammar, actions=self.actions)
    
    @staticmethod
    def make_grammar(start, types):
        # Names and symbols
        names = {}
        symbols = {}
        for i, t in enumerate(types):
            name = f"t{i}_{t.__name__}"
            names[t] = name
            symbols[t] = NonTerminal(name)
            # @generates replaces the original class by a dataclass
            # so if something refers to the original one we need to
            # fix that! (eg. a @skips decorator)
            if hasattr(t, '_orig_type'):
                names[t._orig_type] = name
                symbols[t._orig_type] = symbols[t]
        
        def get_name(symb):
            if isinstance(symb, GrammarSymbol):
                return symb.name
            elif isinstance(symb, str):
                return symb
            return names[symb]
        
        def get_symbol(symb):
            if isinstance(symb, GrammarSymbol):
                return symb
            elif isinstance(symb, str):
                return Terminal(symb, StringRecognizer(symb))
            return symbols[symb]
        
        # Productions and actions
        prods = []
        actions = defaultdict(list)
        for t in types:
            name = get_name(t)
            for ap in t._productions:
                prod = ap.to_parglare(get_symbol)
                prods.append(prod)
                actions[prod.symbol.name].append(ap.action)
        
        prods += _layout_prods
        actions.update(_default_actions)
        
        grammar = Grammar(productions=prods, terminals=[], start_symbol=get_name(start))
        return grammar, actions

    def add_types(self, *extra_types, start=None):
        if start is None:
            start = self.start
        return type(self)(start, *(self.types + extra_types))

    def parse(self, text):
        return self.parser.parse(text)

