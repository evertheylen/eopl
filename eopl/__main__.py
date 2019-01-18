
from eopl.expressions import LET

# TODO load from commandline / interactive shell / file
text = "let x = 1 in (if zero?(x-1) then 100 else 200)"

# TODO let user pick language
prog = LET.parse(text)

# TODO offer option to view parsetree
res = prog.evaluate()

