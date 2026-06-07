from lark import lark
from TypeChecker import TypeChecker
from PrettyPrinter import PrettyPrinter
from CodeGenerator import CodeGenerator


if __name__ == "__main__":
    grammaire = lark.Lark(open("grammar.lark").read(), start="main")
    src = open("source.c").read()
    tree = grammaire.parse(src)
    #print(tree.pretty())

    tc = TypeChecker()
    tc.main(tree)

    pp = PrettyPrinter()
    pp.main(tree)

    cgen = CodeGenerator(tc.node_types, tc.var_offsets, tc.stack_size)
    with open("resultat.asm", "w") as f:
        f.write(cgen.main(tree))

