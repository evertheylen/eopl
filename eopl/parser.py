
from collections import defaultdict
from itertools import chain
import re
from dataclasses import dataclass


# Tokens (bunch of regex's)
# =========================================================

class Token:
    @classmethod
    def tokenize(cls, scanner, token):
        return cls(token)


class _EOS(Token): pass
EOS = _EOS()


class Constant(Token):
    def __init__(self, value):
        self.value = self.TYPE(value)
    
    def __eq__(self, other):
        return type(self) == type(other) and self.value == other.value
    
    __str__ = lambda s: str(s.value)
    __repr__ = lambda s: repr(s.value)



class Integer(Constant):
    TYPE = int
    regex = r'[0-9]+'

class Boolean(Constant):
    TYPE = bool
    regex = r'(true|false)'
    
    @classmethod
    def tokenize(cls, scanner, token):
        return cls(token == 'true')

class String(Constant):
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


all_tokens = [Integer, Boolean, String, Symbol, Punctuation]

scanner = re.Scanner(
    [(cls.regex, cls.tokenize) for cls in all_tokens] + [
        (r'\s+', None),    # whitespace
        (r'%.*\n', None),  # comment
    ]
)



# Grammar
# =========================================================

class Grammar:
    def __init__(self, rules):
        self.rules = rules
        # TODO?


def double(it):
    for i in it:
        yield i, i


class ParserSet:
    def _init_dict(self):
        self.dct = defaultdict(set)
    
    def __init__(self, grammar):
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
            eprint("    {}: {}".format(var, oset(self.dct[var])))


class FIRST(ParserSet):
    def _init_dict(self):
        super()._init_dict()
        self.dct[epsilon] = {epsilon}
        for term in self.G.T: 
            self.dct[term] = {term}
    
    def __call__(self, what):
        if what in self.dct:
            return self.dct[what]
        
        assert isinstance(what, String)
        
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
    def __init__(self, G: Grammar, debug = True):
        self.G = G
        
        if debug:
            eprint(">>> Builing LL(1) Table")
        
        first = FIRST(G)
        follow = FOLLOW(G, first=first)
        
        if debug:
            eprint(" >> FIRST:")
            first.print_vars()
            eprint(" >> FOLLOW:")
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
            self.table = {k: defaultdict(lambda: None, v.flatten()) for k, v in table.items()}
            eprint(">>> Table is built.\n")
        except NotFlat as e:
            #print("!!! Warning: Language is not LL(1)")
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
                cell = self.table[var][term]
                columns[c][r] = str(cell) if cell is not None else ""
        
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
    
    def parse(self, _s: str):
        s = list(_s) + [EOS]
        tree = self._parse(s, self.G.S)
        if s != [EOS]:
            raise Exception("Not all input was processed")
        return tree
    
    def _parse(self, s, var):
        children = []
        string = self.table[var][s[0]]
        for symb in string:
            if symb in self.G.T:
                children.append(symb)
                s.pop(0)
            else:
                children.append(self._parse(s, symb))
        return Tree(var, children)
    

if __name__ == "__main__":
    #G = Grammar({"S", "M", "N"}, {"a", "b", "z"},
            #multimap({"S": {String("zMNz")}, "M": {String("aMa"), String("z")}, "N": {String("bNb"), String("z")}}), "S")
    
    #G = Grammar({"S"}, {"x", "y"},
            #multimap({"S": {String("xSy"), epsilon}}), "S")
    
    G = Grammar.load("/Bestanden/School/MB/voorbeelden/per-topic/LL1/Grune_8.2.4.json")
    
    #G = Grammar({"E", "E'", "T", "T'", "F"}, {"+", "*", "(", ")", "id"},
            #multimap({"E": {Str("T", "E'")}, "E'": {Str("+", "T", "E'"), epsilon}, 
                      #"T": {Str("F", "T'")}, "T'": {Str("*", "F", "T'"), epsilon},
                      #"F": {Str("(", "E", ")"), Str("id")} }), "E")
    #fi = FIRST(G)
    #print("FIRST")
    #fi.print_vars()
    #print()
    #fw = FOLLOW(G, first=fi)
    #fw.print_vars()
    
    print(G)
    parser = LLParser(G)
    print(parser)
    #tree = parser.parse("zaazaabbzbbz")
    #tree.save("test.dot")
    #print(tree)
    #print(tree.terminal_yield())
