
from collections import defaultdict
from itertools import chain
import re
from dataclasses import dataclass

from eopl.util import multimap, NotFlat


# Tokens (bunch of regex's)
# =========================================================

class Token:
    @classmethod
    def tokenize(cls, scanner, token):
        return cls(token)


class Constant(Token):
    def __init__(self, value):
        self.value = self.TYPE(value)
    
    def __eq__(self, other):
        return type(self) == type(other) and self.value == other.value
    
    __str__ = lambda s: str(s.value)
    __repr__ = lambda s: repr(s.value)



class ConstInteger(Constant):
    TYPE = int
    regex = r'[0-9]+'

class ConstBoolean(Constant):
    TYPE = bool
    regex = r'(true|false)'
    
    @classmethod
    def tokenize(cls, scanner, token):
        return cls(token == 'true')

class ConstString(Constant):
    TYPE = str
    regex = r'"(.*)"'
    
    @classmethod
    def tokenize(cls, scanner, token):
        return cls(scanner.match.group(1))


@dataclass
class Symbol(Token):
    name: str
    regex = r'[a-zA-Z?!_][a-zA-Z?!_]*'


class Punctuation(Token, str):
    regex = r'[\(\),\-+*/=]'


_all_tokens = [ConstInteger, ConstBoolean, ConstString, Symbol, Punctuation]

_scanner = re.Scanner(
    [(cls.regex, cls.tokenize) for cls in _all_tokens] + [
        (r'\s+', None),    # whitespace
        (r'%.*\n', None),  # comment
    ]
)


class TokenString(tuple):
    def __str__(self):
        if len(self) == 0: return "ε"
        return "`" + " ".join([str(i) for i in self]) + "`"
    
    __repr__ = __str__
    
    def __add__(self, other):
        return TokenString(tuple(self) + tuple(other))
    
    def __getitem__(self, key):
        if isinstance(key, slice):
            return TokenString(super().__getitem__(key))
        return super().__getitem__(key)



# Grammar
# =========================================================


class Expression:
    pass

@dataclass
class Summation(Expression):
    a: Expression
    b: Expression

@dataclass
class Multiplication(Expression):
    a: Expression
    b: Expression



if __name__ == "__main__":
            
    # E -> ( E )
    # E -> id
    # S -> E + E
    # E -> S
    # M -> E * E
    # E -> M
    
    gram = r"""
    E: '(' E ')' | S | M | number;
    S: E '+' E {left, 1};
    M: E '*' E {left, 2};
    
    terminals
    number: /\d+/;
    """
    
    from parglare import *
    from parglare.grammar import Production, ProductionRHS, ASSOC_NONE, ASSOC_LEFT, ASSOC_RIGHT, RegExRecognizer, StringRecognizer
    
    names = {
        Expression: 'E',
        Summation: 'S',
        Multiplication: 'M',
    }
    
    E = NonTerminal(names[Expression])
    S = NonTerminal(names[Summation])
    M = NonTerminal(names[Multiplication])
    number = Terminal('number', RegExRecognizer(r"\d+"))
    
    all_terminals = set()
    def t(s):
        res = Terminal(s, StringRecognizer(s))
        all_terminals.add(res)
        return res
    
    prods = [
        Production(E, ProductionRHS([t('('), E, t(')')])),
        Production(E, ProductionRHS([S])),
        Production(E, ProductionRHS([M])),
        Production(E, ProductionRHS([number])),
        
        Production(S, ProductionRHS([E, t('+'), E])),
        
        Production(M, ProductionRHS([E, t('*'), E]))
    ]
    
    g = Grammar.from_string(gram)
    g2 = Grammar(productions=prods, terminals=list(all_terminals), start_symbol=names[Expression])
    def skip(p, nodes):
        print("skipping", p, nodes)
        return nodes[0]
    
    parser = Parser(g2, actions={
        'E': [
            skip,
            skip,
            skip,
            lambda _, nodes: (print(f"integer {nodes}"), int(nodes[0]))[1],
        ],
        'S': [lambda _, nodes: (print(f"sum {nodes}"), Summation(nodes[0], nodes[2]))[1]],
        'M': [lambda _, nodes: (print(f"mult {nodes}"), Multiplication(nodes[0], nodes[2]))[1]],
    })
    res = parser.parse("34 + 2 * 4")
    print("RESULT", res)
    import pdb
    pdb.set_trace()

