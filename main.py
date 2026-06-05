from lark import lark
from TypeChecker import TypeChecker
from PrettyPrinter import PrettyPrinter


if __name__ == "__main__":
    grammaire = lark.Lark(open("grammar.lark").read(), start="main")
    src = open("source.c").read()
    tree = grammaire.parse(src)
    #print(tree.pretty())

    pp = PrettyPrinter()
    print(pp.visit(tree))


    tc = TypeChecker()
    tc.main(tree)

