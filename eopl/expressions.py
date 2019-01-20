
from eopl.parser import *

@skip('(', None, ')')
class Expression:
    pass


@generates(Field('a', Expression), '+', Field('b', Expression), assoc='left', priority=1200)
@replaces(Expression)
class Summation:
    def evaluate(self):
        return self.a.evaluate() + self.b.evaluate()

    
@generates(Field('a', Expression), '*', Field('b', Expression), assoc='left', priority=1100)
@replaces(Summation)
class Multiplication:
    def evaluate(self):
        return self.a.evaluate() * self.b.evaluate()

    
@generates(Field('val', Number))
@replaces(Expression)
class Constant:
    def evaluate(self):
        return self.val
    

MATH = Language(Expression, Summation, Multiplication, Constant)


if __name__ == "__main__":
    expr = MATH.parse("5 + 3 * 2")
    print(expr)
    print(expr.evaluate())
