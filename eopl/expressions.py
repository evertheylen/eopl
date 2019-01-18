
class Expression:
    pass


@rule(Symbol("zero?"), "(", Field('expr', Expression), ")")
class IsZero(Expression):
    pass
    

@rule
class Program:
    expr: Expression
