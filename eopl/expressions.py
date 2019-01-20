
import operator
from collections import ChainMap

from eopl.parser import *


def make_binary_operator(_name, _cls, _op, _func, _priority, _assoc='left'):
    def f(name=_name, cls=_cls, op=_op, func=_func, priority=_priority, assoc=_assoc):
        @generates(Field('a', cls), op, Field('b', cls), assoc=assoc, priority=priority)
        @replaces(cls)
        class Operator:
            def evaluate(self, *a, **kw):
                return func(self.a.evaluate(*a, **kw), self.b.evaluate(*a, **kw))
        Operator.__name__ = name
        Operator.__qualname__ = name
        return Operator
    return f()


def make_unary_operator(_name, _cls, _op, _func, _priority):
    def f(name=_name, cls=_cls, op=_op, func=_func, priority=_priority):
        @generates(op, Field('a', cls), priority=priority)
        @replaces(cls)
        class Operator:
            def evaluate(self, *a, **kw):
                return func(self.a.evaluate(*a, **kw))
        Operator.__name__ = name
        Operator.__qualname__ = name
        return Operator
    return f()


Environment = ChainMap


@skip('(', THIS, ')')
class Expression:
    pass


@generates(Field('expr', Expression))
class LetProgram:
    def evaluate(self):
        env = Environment()
        return self.expr.evaluate(env) 
    

@generates(Field('val', Number))
@generates(Field('val', Boolean))
@generates(Field('val', String))
@replaces(Expression)
class Constant:
    def evaluate(self, *args, **kwargs):
        return self.val


@generates(Field('name', RawIdentifier))
@replaces(Expression)
class Identifier:
    def evaluate(self, env, *args, **kwargs):
        return env[self.name]


@generates('let', Field('var', RawIdentifier), '=', Field('value', Expression), 'in', Field('expr', Expression))
@replaces(Expression)
class LetExpr:
    def evaluate(self, env, *args, **kwargs):
        new_env = env.new_child({self.var: self.value.evaluate(env, *args, **kwargs)})
        return self.expr.evaluate(new_env, *args, **kwargs)


@generates('if', Field('cond', Expression), 'then', Field('true', Expression), 'else', Field('false', Expression))
@replaces(Expression)
class IfExpr:
    def evaluate(self, *args, **kwargs):
        if self.cond.evaluate(*args, **kwargs):
            return self.true.evaluate(*args, **kwargs)
        else:
            return self.false.evaluate(*args, **kwargs)


Neg = make_unary_operator('Neg', Expression, '-', operator.neg, 1300)

Mul = make_binary_operator('Mul', Expression, '*', operator.mul, 1200)
Div = make_binary_operator('Div', Expression, '/', operator.floordiv, 1200)
Mod = make_binary_operator('Mod', Expression, 'mod', operator.mod, 1200)

Add = make_binary_operator('Add', Expression, '+', operator.add, 1100)
Sub = make_binary_operator('Sub', Expression, '-', operator.sub, 1100)

math_ops = [Neg, Add, Sub, Mul, Div, Mod]

Eq = make_binary_operator('Eq', Expression, '==', operator.eq, 1000)
Ne = make_binary_operator('Ne', Expression, '!=', operator.ne, 1000)
Lt = make_binary_operator('Lt', Expression, '<', operator.lt, 1000)
Le = make_binary_operator('Le', Expression, '<=', operator.le, 1000)
Gt = make_binary_operator('Gt', Expression, '>', operator.gt, 1000)
Ge = make_binary_operator('Ge', Expression, '>=', operator.ge, 1000)

comp_ops = [Eq, Ne, Lt, Le, Gt, Ge]

And = make_binary_operator('And', Expression, 'and', operator.and_, 900)
Or  = make_binary_operator('Or', Expression, 'or', operator.or_, 900)
Not = make_unary_operator('Not', Expression, 'not', operator.not_, 900)

logic_ops = [And, Or, Not]

basics = [Expression, Constant, Identifier, *math_ops, *comp_ops, *logic_ops]

LET = Language(LetProgram, LetExpr, IfExpr, *basics)



# Tests
# ===============================================

import unittest

class TestLet(unittest.TestCase):
    def test_math(self):
        res = LET.parse("50 + 3 * 2").evaluate()
        self.assertEqual(res, 56)
    
    def test_let(self):
        res = LET.parse("let x = 5 in x + 9").evaluate()
        self.assertEqual(res, 14)
    
    def test_complex(self):
        s = """
        let foo = 5 in
        let bar = (foo * 2) in
        if foo < bar and bar mod 2 == 0 then 
            "as it should be"
        else
            "something is wrong"
        """
        res = LET.parse(s).evaluate()
        self.assertEqual(res, "as it should be")


if __name__ == '__main__':
    unittest.main()
