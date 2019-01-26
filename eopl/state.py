
from dataclasses import dataclass, field
from weakref import WeakKeyDictionary

from eopl.language import *
from eopl.base import *
from eopl.expressions import *


@dataclass(frozen=True)
class Reference:
    ptr: int
    __str__ = __repr__ = lambda s: hex(s.ptr)


# weakref -> free GC :)
class Store(WeakKeyDictionary):
    def newref(self) -> Reference:
        return Reference(len(self))
    
    def deref(self, ref: Reference):
        assert isinstance(ref, Reference)
        return self[ref]
    
    def setref(self, ref: Reference, val):
        assert isinstance(ref, Reference)
        self[ref] = val


@make_list(Expression, ';')
class ExprList(list):
    pass


@generates('begin', Field('expressions', ExprList), 'end')
@replaces(Expression)
class BeginEnd(BaseExpr):
    def evaluate(self, ctx):
        for e in self.expressions:
            res = e.evaluate(ctx)
        return res
        
    def free_vars(self):
        for e in self.expressions:
            yield from e.free_vars()



# EXPLICIT_REFS: A Language with Explicit References
# ==================================================

@generates('newref', '(', Field('init_expr', Expression), ')')
@replaces(Expression)
class NewRefExpr(BaseExpr):
    def evaluate(self, ctx):
        ref = ctx.store.newref()
        init = self.init_expr.evaluate(ctx)
        ctx.store.setref(ref, init)
        return ref
    

@generates('deref', '(', Field('ref', Expression), ')')
@replaces(Expression)
class DeRefExpr(BaseExpr):
    def evaluate(self, ctx):
        ref = self.ref.evaluate(ctx)
        assert isinstance(ref, Reference)
        return ctx.store.deref(ref)


@generates('setref', '(', Field('ref', Expression), ',', Field('val', Expression), ')')
@replaces(Expression)
class SetRefExpr(BaseExpr):
    def evaluate(self, ctx):
        ref = self.ref.evaluate(ctx)
        assert isinstance(ref, Reference)
        val = self.val.evaluate(ctx)
        ctx.store.setref(ref, val)
        return val


@dataclass
class StoreContext(Context):
    store: Store = field(default_factory=Store)


@generates(Field('expr', Expression))
@upgrades(LetProgram)
class ExplRefProgram(Start):
    def evaluate(self):
        ctx = StoreContext()
        return self.expr.evaluate(ctx)


EXPLICIT_REFS = LETREC.add_types(BeginEnd, ExprList, NewRefExpr, DeRefExpr, SetRefExpr, ExplRefProgram)



# IMPLICIT_REFS: A Language with Implicit References
# ==================================================

@upgrades(Identifier)
class DerefIdentifier(Identifier):
    def evaluate(self, ctx):
        ref = super().evaluate(ctx)
        return ctx.store.deref(ref)


@generates('set', Field('var', RawIdentifier), '=', Field('value', Expression))
@replaces(Expression)
class ImplicitSetRef(BaseExpr):
    def evaluate(self, ctx):
        ref = ctx.env[self.var]
        val = self.value.evaluate(ctx)
        ctx.store.setref(ref, val)
        return val
    
    def free_vars(self):
        yield self.var
        yield from self.value.free_vars()


@upgrades(CallExpr)
class CallByReferenceExpr(CallExpr):
    # The default CallExpr will evaluate the argument, then store it and pass
    # the resulting reference to Procedure.call (through ctx.wrap).
    # This is different, we don't need to add a new store if we're passing
    # variables directly!
    def evaluate(self, ctx):
        proc = self.proc.evaluate(ctx)
        if isinstance(self.arg, DerefIdentifier):
            arg = ctx.env[self.arg.name]
        else:
            arg = ctx.wrap(self.arg.evaluate(ctx))
        return proc.call(arg, ctx)


class ImplicitStoreContext(StoreContext):
    def wrap(self, val):
        ref = self.store.newref()
        self.store.setref(ref, val)
        return ref
    
    def with_layer(self, l):
        assert all(isinstance(v, Reference) for v in l.values()), f"Environment contains non-references!"
        return super().with_layer(l)


@generates(Field('expr', Expression))
@upgrades(LetProgram)
class ImplRefProgram(Start):
    def evaluate(self):
        ctx = ImplicitStoreContext()
        return self.expr.evaluate(ctx)


IMPLICIT_REFS = LETREC.add_types(BeginEnd, ExprList, DerefIdentifier, ImplicitSetRef, CallByReferenceExpr, ImplRefProgram)


# Tests
# ===============================================

import unittest


class ExplicitRefsTest(unittest.TestCase):
    def test_simple(self):
        s = """
        let g = 
            let counter = newref(0) in proc (dummy)
                begin
                    setref(counter, deref(counter) + 1);
                    deref(counter)
                end
        in let a = g(11); b = g(11)
        in a - b
        """
        res = EXPLICIT_REFS.parse(s).evaluate()
        self.assertEqual(res, -1)


class ImplicitRefsTest(unittest.TestCase):
    def test_simple(self):
        s = """
        let g = 
            let count = 0 in proc (dummy)
                begin
                    set count = count + 1;
                    count
                end
        in let a = g(11); b = g(11)
        in a - b
        """
        res = IMPLICIT_REFS.parse(s).evaluate()
        self.assertEqual(res, -1)
    
    def test_cbr(self):
        s = """
        let manual_set = proc (x) proc (val) set x = val
        in 
            let foo = -10; bar = -20 in
                begin
                    manual_set(foo)(42);
                    manual_set(bar)(8);
                    foo + bar
                end
        """
        res = IMPLICIT_REFS.parse(s).evaluate()
        self.assertEqual(res, 50)


if __name__ == '__main__':
    unittest.main()
