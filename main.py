from lark import lark
from TypeChecker import TypeChecker
from PrettyPrinter import PrettyPrinter
from CodeGenerator import CodeGenerator


if __name__ == "__main__":
    grammaire = lark.Lark(open("grammar.lark").read(), start="main")
    src = open("source.c").read()
    tree = grammaire.parse(src)
    #print(tree.pretty())

    pp = PrettyPrinter()
    pp.visit(tree)

    tc = TypeChecker()
    tc.main(tree)

    cgen = CodeGenerator(tc.node_types, tc.toutes_les_variables)
    with open("resultat.asm", "w") as f:
        f.write(cgen.main(tree))

