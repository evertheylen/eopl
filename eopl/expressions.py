
@skip('(', None, ')')
class Expression:
    pass

# E -> ( E )


@generates(Field('a', Expression), '+', Field('b', Expression))
@replaces(Expression)
class Summation:
    pass

# S -> E + E
# E -> S

    
@generates(Field('a', Expression), '*', Field('b', Expression))
@replaces(Summation)
class Multiplication:
    pass

# M -> E * E
# E -> M


@rule(Symbol("zero?"), "(", Field('expr', Expression), ")")
class IsZero(Expression):
    pass
    

@rule
class Program:
    expr: Expression
