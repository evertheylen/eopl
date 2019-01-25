
import operator
from dataclasses import dataclass

from eopl.base import *
from eopl.parser import *



# LET: A Simple Language
# ===============================================

def make_binary_operator(_name, _cls, _op, _func, _priority, _assoc='left'):
    def f(name=_name, cls=_cls, op=_op, func=_func, priority=_priority, assoc=_assoc):
        @generates(Field('a', cls), op, Field('b', cls), assoc=assoc, priority=priority)
        @replaces(cls)
        class Operator(BaseExpr):
            def evaluate(self, ctx):
                return func(self.a.evaluate(ctx), self.b.evaluate(ctx))
        Operator.__name__ = name
        Operator.__qualname__ = name
        return Operator
    return f()


def make_unary_operator(_name, _cls, _op, _func, _priority):
    def f(name=_name, cls=_cls, op=_op, func=_func, priority=_priority):
        @generates(op, Field('a', cls), priority=priority)
        @replaces(cls)
        class Operator(BaseExpr):
            def evaluate(self, ctx):
                return func(self.a.evaluate(ctx))
        Operator.__name__ = name
        Operator.__qualname__ = name
        return Operator
    return f()


@skip('(', THIS, ')')
class Expression(BaseExpr):
    pass


@generates(Field('expr', Expression))
class LetProgram:
    def evaluate(self):
        ctx = Context()
        return self.expr.evaluate(ctx)
    

@generates(Field('val', Number))
@generates(Field('val', Boolean))
@generates(Field('val', String))
@replaces(Expression)
class Constant(BaseExpr):
    def evaluate(self, ctx):
        return self.val
    
    def free_vars(self):
        return; yield


@generates(Field('name', RawIdentifier))
@replaces(Expression)
class Identifier(BaseExpr):
    def evaluate(self, ctx):
        if self.name not in ctx.env:
            raise Exception(f"Couldn't find {self.name} in:\n{pretty(ctx.env)}")
        return ctx.env[self.name]

    def free_vars(self):
        yield self.name


@generates('let', Field('var', RawIdentifier), '=', Field('value', Expression), 'in', Field('expr', Expression))
@replaces(Expression)
class LetExpr(BaseExpr):
    def evaluate(self, ctx):
        sub_ctx = ctx.with_layer({self.var: self.value.evaluate(ctx)})
        return self.expr.evaluate(sub_ctx)


@generates('if', Field('cond', Expression), 'then', Field('true', Expression), 'else', Field('false', Expression))
@replaces(Expression)
class IfExpr(BaseExpr):
    def evaluate(self, ctx):
        if self.cond.evaluate(ctx):
            return self.true.evaluate(ctx)
        else:
            return self.false.evaluate(ctx)


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



# PROC: A Language with Procedures
# ================================

@dataclass
class DynamicProcedure:
    argname: str
    body: Expression
    
    def call(self, arg, ctx):
        call_ctx = ctx.with_layer({self.argname: arg})
        return self.body.evaluate(call_ctx)


@dataclass
class Procedure(DynamicProcedure):
    bound: dict
    
    def call(self, arg, ctx):
        call_ctx = Context().with_layer(self.bound).with_layer({self.argname: arg})
        return self.body.evaluate(call_ctx)


@generates('proc', '(', Field('arg', RawIdentifier), ')', Field('body', Expression))
@replaces(Expression)
class DynProcExpr(BaseExpr):
    def evaluate(self, ctx):
        return DynamicProcedure(self.arg, self.body)
        
    def free_vars(self):
        for v in self.body.free_vars():
            if v != self.arg:
                yield v


class ProcExpr(DynProcExpr):
    def evaluate(self, ctx):
        bound = {v: ctx.env[v] for v in self.free_vars()}
        return Procedure(self.arg, self.body, bound)


# TODO: Slight parser problem: the original definition (f arg) confuses
# infix operators with function calls...
@generates(Field('proc', Expression), '(', Field('arg', Expression), ')')
@replaces(Expression)
class CallExpr(BaseExpr):
    def evaluate(self, ctx):
        proc = self.proc.evaluate(ctx)
        arg = self.arg.evaluate(ctx)
        return proc.call(arg, ctx)
    

PROC = LET.add_types(ProcExpr, CallExpr)
DYNPROC = LET.add_types(DynProcExpr, CallExpr)


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


class TestProc(unittest.TestCase):
    def test_simple(self):
        s = """
        let a = 5 in
        let f = proc (b) a+b in
        f(3)
        """
        res = PROC.parse(s).evaluate()
        self.assertEqual(res, 8)
    
    def test_complex(self):
        s = """
        let chain = proc(f1) proc(f2) proc(x) f2(f1(x)) in
        let add_one = proc(x) x+1 in
        let mult_two = proc(x) x*2 in
        chain(add_one)(mult_two)(5)
        """
        res = PROC.parse(s).evaluate()
        self.assertEqual(res, 12)
    
    def test_exam_static(self):
        s = """
        let f = proc(x) 1 in
            let f = proc(y) if y == 0 then 0 else f(y-1) in
                f(2)
        """
        res = PROC.parse(s).evaluate()
        self.assertEqual(res, 1)
    
    def test_exam_dynamic(self):
        s = """
        let f = proc(x) 1 in
            let f = proc(y) if y == 0 then 0 else f(y-1) in
                f(2)
        """
        res = DYNPROC.parse(s).evaluate()
        self.assertEqual(res, 0)


if __name__ == '__main__':
    unittest.main()
