
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


class _EOS(Token):
    __str__ = __repr__ = lambda s: "<EOS>"
EOS = _EOS()


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


epsilon = TokenString([])  # empty string


def tokenize(text: str) -> TokenString:
    raw_tokens, rest = _scanner.scan(text)
    if len(rest) != 0:
        raise Exception(f"Untokenized text remains: {rest!r}")
    return TokenString(raw_tokens)
    


# Grammar
# =========================================================


class Grammar:
    def __init__(self, V, T, P, S):
        self.V = V  # Variables
        self.T = T  # Terminals
        self.P = P  # Productions
        self.S = S  # Start Variable
        assert S in V
        for var, string in P.flat_items():
            assert var in V
            for symb in string:
                assert symb in self.symbols, f"{symb} not in {self.symbols}"
        assert len(V & T) == 0, "The intersection of V and T must be empty"
    
    def __str__(self):
        s =  "Variables = " + ", ".join(map(str, sorted(self.V))) + "\n"
        s += "Terminals = " + ", ".join(map(str, sorted(self.T))) + "\n"
        s += "Productions = {\n"
        for var in sorted(self.V):
            for string in sorted(self.P[var]):
                s += f"    {var} \t-> {string}\n"
        s += "}\n"
        s += f"Start = {self.S}"
        return s
    
    @property
    def invP(self):
        if not hasattr(self, "_invP"):
            # Inverse of P
            self._invP = multimap()
            for var, string in self.P.flat_items():
                self._invP[string].add(var)
        return self._invP
    
    @property
    def symbols(self):
        if not hasattr(self, "_symbols"):
            self._symbols = self.V | self.T
        return self._symbols
    


def double(it):
    for i in it:
        yield i, i


class ParserSet:
    def _init_dict(self):
        self.dct = defaultdict(set)
    
    def __init__(self, G: Grammar):
        self.G = G
        self._init_dict()
        
        while True:
            old_dct = {k: v.copy() for k,v in self.dct.items()}
            self._step()
            if self.dct == old_dct:
                break
    
    def __call__(self, what):
        return self.dct[what]
    
    def print_vars(self):
        for var in sorted(self.G.V):
            print("    {}: {}".format(var, oset(self.dct[var])))


class FIRST(ParserSet):
    def _init_dict(self):
        super()._init_dict()
        self.dct[epsilon] = {epsilon}
        for term in self.G.T: 
            self.dct[term] = {term}
    
    def __call__(self, what):
        if what in self.dct:
            return self.dct[what]
        
        assert isinstance(what, TokenString)
        
        if len(what) == 1:
            return self(what[0])  # Important :)
        
        assert len(what) > 1
        
        res = self.dct[what[0]]
        if epsilon in res:
            res = (res - {epsilon}) | self(what[1:])
        self.dct[what] = res
        return res
    
    def _step(self):
        for X, string in chain(self.G.P.flat_items()):
            if string != epsilon:
                self.dct[X].update(self.dct[string[0]] - {epsilon})
            for i in range(len(string)-1):
                Y1 = string[i]
                Y2 = string[i+1]
                if epsilon in self.dct[Y1]:
                    self.dct[X].update(self.dct[Y2] - {epsilon})
            if all(epsilon in self.dct[Y] for Y in string):
                self.dct[X].add(epsilon)


class FOLLOW(ParserSet):
    def __init__(self, G: Grammar, first = None):
        if first is None:
            first = FIRST(G)
        self.first = first
        super().__init__(G)
    
    def _init_dict(self):
        super()._init_dict()
        self.dct[self.G.S].add(EOS)
    
    def _step(self):
        for var, string in self.G.P.flat_items():
            for i, A in enumerate(string):
                if A in self.G.V:
                    # alpha = string[:i]
                    beta = string[i+1:]
                    
                    if len(beta) > 0:
                        self.dct[A].update(self.first(beta) - {epsilon})
                    else:
                        self.dct[A].update(self.dct[var])
                    if epsilon in self.first(beta):
                        self.dct[A].update(self.dct[var])
    

class LLParser:
    def __init__(self, G: Grammar, debug = False):
        self.G = G
        
        if debug:
            print(">>> Builing LL(1) Table")
        
        first = FIRST(G)
        follow = FOLLOW(G, first=first)
        
        if debug:
            print(" >> FIRST:")
            first.print_vars()
            print(" >> FOLLOW:")
            follow.print_vars()
        
        table = defaultdict(multimap)
        
        for var, string in G.P.flat_items():
            for symb in first(string):
                if symb == epsilon:
                    for term in follow(var):
                        table[var][term].add(string)
                else:  # symb is a terminal
                    table[var][symb].add(string)
        
        try:
            self.table = {k: v.flatten() for k, v in table.items()}
            print(">>> Table is built.\n")
        except NotFlat as e:
            raise Exception("Language is not LL(1)") from e
    
        
    
    def __str__(self):
        terminals = sorted(self.G.T, key=str) + [EOS]
        variables = sorted(self.G.V, key=str)
        
        columns = []
        for i in range(len(self.G.T) + 2):  # row headers and EOS
            columns.append([""] * (len(self.G.V) + 1))
        
        # Headers
        columns[0] = [""] + list(map(str, variables))
        for i in range(1, len(columns)):
            columns[i][0] = str(terminals[i-1])
        
        # Rest of the data
        for _c, term in enumerate(terminals):
            c = _c + 1
            for _r, var in enumerate(variables):
                r = _r + 1
                columns[c][r] = str(self.table[var].get(term, ""))
        
        col_lengths = [max(map(len, ln)) for ln in columns]
        
        lines = []
        line = []
        for c in range(len(columns)):
            val = columns[c][0]
            line.append(val.ljust(col_lengths[c]))
        lines.append("  " + "  | ".join(line) + "  |")
        horizontal_line = "|-" + "--|-".join("-"*col_lengths[i] for i in range(len(columns))) + "--|"
        lines.append(horizontal_line)
        for r in range(1, len(columns[0])):
            line = []
            for c in range(len(columns)):
                val = columns[c][r]
                line.append(val.ljust(col_lengths[c]))
            lines.append("| " + "  | ".join(line) + "  |")
        lines.append(horizontal_line)
        
        return "\n".join(lines)
    
    def parse(self, s: TokenString):
        to_parse = list(s) + [EOS]
        parsed = []
        tree = self._parse(to_parse, parsed, self.G.S)
        if to_parse != [EOS]:
            raise Exception("Not all input was processed")
        return tree
    
    def _parse(self, to_parse, parsed, var):
        children = []
        string = self.table[var].get(to_parse[0])
        if string is None:
            raise Exception(f"String did not satisfy language (variable {var}, already parsed {parsed})")
        for symb in string:
            if symb in self.G.T:
                children.append(symb)
                parsed.append(to_parse.pop(0))
            else:
                children.append(self._parse(to_parse, parsed, symb))
        return Tree(var, children)


class Tree:
    def __init__(self, content, children = []):
        self.content = content
        self.children = children
    
    def __str__(self):
        return "(" + str(self.content) + " " + " ".join(map(str, self.children)) + ")"


if __name__ == "__main__":
    
    print("TOKENIZE")
    print(tokenize("if iszero? (x) then let x = 1 in x + 1 else x + (x * 2)"))
    
    def Str(*l):
        return TokenString(l)
    
    #G = Grammar({"S", "M", "N"}, {"a", "b", "z"},
            #multimap({"S": {String("zMNz")}, "M": {String("aMa"), String("z")}, "N": {String("bNb"), String("z")}}), "S")
    
    #G = Grammar({"S"}, {"x", "y"},
            #multimap({"S": {String("xSy"), epsilon}}), "S")
            
    # E -> ( E )
    # E -> id
    # S -> E + E
    # E -> S
    # M -> E * E
    # E -> M
    
    
    grammar = r"""
    E: '(' E ')' | S | M | number;
    S: E '+' E {left, 1};
    M: E '*' E {left, 2};
    
    terminals
    number: /\d+/;
    """
    
    from parglare import Parser, Grammar
    
    g = Grammar.from_string(grammar)
    parser = Parser(g)
    res = parser.parse("34 + 2 * 4")
    print("RESULT", res)
    
    """
    P = multimap({
        "E": {Str("(", "E", ")"), Str("id"), Str("S"), Str("M")},
        "S": {Str("E", "+", "E")},
        "M": {Str("E", "*", "E")},
    })
    
    G = Grammar({"E", "S", "M"}, {"+", "*", "(", ")", "id"}, P, "E")
    
    print(G)
    parser = LLParser(G)
    print(parser)
    tree = parser.parse(Str("id", "+", "id", "*", "id"))
    print(tree)
    """
