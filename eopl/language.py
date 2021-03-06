
from collections import defaultdict
from dataclasses import dataclass, field, make_dataclass, MISSING
from typing import Callable, Any

from parglare import Parser, Grammar
from parglare.grammar import Production, ProductionRHS, Terminal, NonTerminal, GrammarSymbol, \
    RegExRecognizer, StringRecognizer, \
    ASSOC_NONE, ASSOC_LEFT, ASSOC_RIGHT, \
    LAYOUT, LAYOUT_ITEM, WS, EMPTY

from eopl.util import multimap

__all__ = ('Field', 'skip', 'THIS', 'generates', 'replaces', 'upgrades', 'make_list',
           'Number', 'Boolean', 'String', 'RawIdentifier', 'Language', 'Start')


# Declare Grammar
# ===============================================


Action = Callable[[Any, list], Any]


class Start:
    pass


@dataclass
class AbstractProduction:
    head: type
    body: list  # should only contain classes (to be translated)
    action: Action = None
    priority: int = 100
    assoc: str = 'none'
    
    def __post_init__(self):
        assert self.assoc in ['left', 'right', 'none']
    
    def to_parglare(self, defining_type, get_symbol):
        head = get_symbol(defining_type if self.head is None else self.head)
        body = ProductionRHS([get_symbol(defining_type if s is None else s) for s in self.body])
        assoc = {'none': ASSOC_NONE, 'left': ASSOC_LEFT, 'right': ASSOC_RIGHT}[self.assoc]
        return Production(symbol=head, rhs=body, assoc=assoc, prior=self.priority)
    
    def make_action(self, defining_type):
        return self.action(defining_type)


@dataclass(frozen=True)
class Field:
    name: str
    type: type
    default: Any = None
    
    def make_dc_field(self):
        return (self.name, self.type, field(default=(MISSING if self.default is None else self.default)))


def add_tags(cls):
    if '_productions' not in vars(cls):
        setattr(cls, '_productions', getattr(cls, '_productions', []).copy())
        setattr(cls, '_fields', getattr(cls, '_fields', None))
        setattr(cls, '_upgrade_from', getattr(cls, '_upgrade_from', []).copy())


THIS = None

def skip(*symbols, **kwargs):
    def f(cls):
        add_tags(cls)
        if symbols.count(None) != 1:
            raise Exception("@skip needs exactly one mention of 'None' aka THIS")
        index = symbols.index(None)
        cls._productions.append(AbstractProduction(
            head=None,
            body=symbols,  # [(cls if s is None else s) for s in symbols],
            action=lambda _: lambda _, nodes, _index=index: nodes[_index],
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
            #cls._orig_type = orig_cls
            
        elif fields.keys() != cls._fields.keys():
            # TODO check defaults
            raise Exception("Fields on class differ!")
        
        def action(cls, field_index=field_index):
            def _action(_, nodes, cls=cls, field_index=field_index):
                return cls(**{name: nodes[i] for name, i in field_index.items()})
            return _action
        
        raw_symbols = [(s.type if isinstance(s, Field) else s) for s in symbols]
        cls._productions.append(AbstractProduction(None, raw_symbols, action, **kwargs))
        return cls
    return f


def replaces(from_cls, **kwargs):
    def f(cls):
        add_tags(cls)
        cls._productions.append(AbstractProduction(from_cls, [None], action=lambda _: lambda _, nodes: nodes[0], **kwargs))
        return cls
    return f


def upgrades(from_cls):
    def f(cls):
        add_tags(cls)
        cls._upgrade_from.append(from_cls)
        return cls
    return f


@dataclass(frozen=True)
class TempSymbol:
    name: str


def make_list(t, divider, empty=False):
    def f(cls):
        add_tags(cls)
        helper_symb = TempSymbol(f"_list_{cls.__name__}_{t.__name__}")
        # TODO: prevent other productions?
        
        # Forward the list
        cls._productions.append(AbstractProduction(None, [helper_symb], action=lambda _cls: lambda _, nodes: _cls(nodes[0])))
        
        if empty:  # empty list
            cls._productions.append(AbstractProduction(helper_symb, [], action=lambda _: lambda _, nodes: []))
        # single member
        cls._productions.append(AbstractProduction(helper_symb, [t], action=lambda _: lambda _, nodes: [nodes[0]]))
        #cls._productions.append(AbstractProduction(helper_symb, [t, divider], action=lambda _: lambda _, nodes: [nodes[0]]))
        # two members
        cls._productions.append(AbstractProduction(helper_symb, [t, divider, helper_symb],
                                                   action=lambda _: lambda _, nodes: [nodes[0]] + nodes[2]))
        return cls
    return f


# Grammar extra's
# ===============================================

_default_actions = {
    'Number': lambda _, s: int(s),
    'Boolean': lambda _, s: s == 'true',
    'String': lambda _, s: s[1:-1],
    'RawIdentifier': lambda _, s: s
}

Number = Terminal('Number', RegExRecognizer(r"\d+"))
Boolean = Terminal('Boolean', RegExRecognizer(r"(true|false)"))
Boolean.prior = 100
String = Terminal('String', RegExRecognizer(r'".*"'))
RawIdentifier = Terminal('RawIdentifier', RegExRecognizer(r'[A-Za-z_][A-Za-z0-9_]*'))

_comment = Terminal('_comment', RegExRecognizer(r"%.*\n"))

_layout_prods = [
    Production(LAYOUT, ProductionRHS([LAYOUT_ITEM])),
    Production(LAYOUT, ProductionRHS([LAYOUT, LAYOUT_ITEM])),
    Production(LAYOUT_ITEM, ProductionRHS([WS])),
    Production(LAYOUT_ITEM, ProductionRHS([_comment])),
    Production(LAYOUT_ITEM, ProductionRHS([EMPTY])),
]

_default_symbols = [Number, Boolean, String, RawIdentifier, _comment]



# Make an actual language!
# =========================================================


class Language:
    def __init__(self, *types):
        types = list(types)
        upgrade_map = {}
        for t in types:
            for repl in t._upgrade_from:
                if repl in upgrade_map:
                    raise Exception(f"Can't upgrade {repl} both to {upgrade_map[repl]} and {t}")
                upgrade_map[repl] = t
        
        # Keep the order, but don't allow duplicate types
        self.types = []
        added = set()
        for t in types:
            actual_t = upgrade_map.get(t, t)
            if actual_t not in added:
                added.add(actual_t)
                self.types.append(actual_t)
            
        start_types = [t for t in self.types if issubclass(t, Start)]
        if len(start_types) != 1:
            raise Exception(f"There was no unique starting NonTerminal (instead got {start_types})")
        self.start = start_types[0]
            
        self.grammar, self.actions = self.make_grammar(self.start, self.types)
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
            for repl in t._upgrade_from:
                names[repl] = name
                symbols[repl] = symbols[t]
            
            # @generates replaces the original class by a dataclass
            # so if something refers to the original one we need to
            # fix that! (eg. a @skips decorator)
            if hasattr(t, '_orig_type'):
                names[t._orig_type] = name
                symbols[t._orig_type] = symbols[t]
        
        def get_name(symb):
            if isinstance(symb, (GrammarSymbol, TempSymbol)):
                return symb.name
            elif isinstance(symb, str):
                return symb
            return names[symb]
        
        def get_symbol(symb):
            if isinstance(symb, GrammarSymbol):
                return symb
            elif isinstance(symb, str):
                return Terminal(symb, StringRecognizer(symb))
            try:
                return symbols[symb]
            except KeyError as e:
                if isinstance(symb, TempSymbol):
                    symbols[symb] = NonTerminal(symb.name)
                    return symbols[symb]
                else:
                    raise e
        
        # Productions and actions
        prods = []
        actions = defaultdict(list)
        for t in types:
            name = get_name(t)
            for ap in t._productions:
                prod = ap.to_parglare(t, get_symbol)
                prods.append(prod)
                actions[prod.symbol.name].append(ap.make_action(t))
        
        prods += _layout_prods
        actions.update(_default_actions)
        grammar = Grammar(productions=prods, terminals=[], start_symbol=get_name(start))
        return grammar, actions

    def add_types(self, *extra_types):
        return type(self)(*self.types, *extra_types)

    def parse(self, text):
        return self.parser.parse(text)

