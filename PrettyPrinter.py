from lark import Tree


class PrettyPrinter:

    def visit(self, node):
        # Cas d'une feuille
        if not isinstance(node, Tree):
            return node

        rule = node.data
        methode = getattr(self, rule, None)  # plus simple qu'une série de if/else

        if methode is None:
            raise NotImplementedError(
                f"il n'y a pas de méthode pour la rêgle de grammaire '{rule}'."
            )

        return methode(node)

    # EXPRESSIONS
    def entier(self, tree):
        return tree.children[0].value

    def double(self, tree):
        return tree.children[0].value

    def chaine(self, tree):
        return tree.children[0].value

    def full_type(self, tree):

        if len(tree.children) == 1:
            return tree.children[0].value

        key_type = tree.children[1].value
        value_type = self.visit(tree.children[2])
        return f"dict<{key_type},{value_type}>"

    def binaire(self, tree):
        return f"{self.visit(tree.children[0])} {tree.children[1].value} {self.visit(tree.children[2])}"

    def variable(self, tree):
        return tree.children[0].value

    def dict_access(self, tree):
        return f"{tree.children[0].value}[{self.visit(tree.children[1])}]"

    def dict_literal(self, tree):
        return f"{{{', '.join(f'{self.visit(k)}: {self.visit(v)}' for k, v in zip(tree.children[0::2], tree.children[1::2]))}}}"

    def conversion(self, tree):
        return f"{tree.children[0].value}({self.visit(tree.children[1])})"

    def non_logique(self, tree):
        return f"!{self.visit(tree.children[0])}"

    def parenthese(self, tree):
        return f"({self.visit(tree.children[0])})"

    def atoi(self, tree):
        return f"atoi({self.visit(tree.children[0])})"

    def length(self, tree):
        return f"len({self.visit(tree.children[0])})"

    def charat(self, tree):
        return f"charat({self.visit(tree.children[0])}, {self.visit(tree.children[1])})"

    # COMMANDES

    def assignation(self, tree):
        return f"{tree.children[0].value} = {self.visit(tree.children[1])};"

    def decl_assignation(self, tree):
        return f"{self.visit(tree.children[0])} = {self.visit(tree.children[1])};"

    def assignation_dict(self, tree):
        return f"{tree.children[0].value}[{self.visit(tree.children[1])}] = {self.visit(tree.children[2])};"

    def decl(self, tree):
        return f"{self.visit(tree.children[0])} {tree.children[1].value}"

    def nop(self, tree):
        return "pass"

    def print(self, tree):
        return f"print({self.visit(tree.children[0])});"

    def bloc(self, tree):
        return "{" + "\n".join(self.visit(child) for child in tree.children) + "}"

    def block_while(self, tree):
        return f"while ({self.visit(tree.children[0])})\n{self.visit(tree.children[1])}\n"

    def block_if(self, tree):
        return f"if ({self.visit(tree.children[0])})\n{self.visit(tree.children[1])}\n"

    def foreach(self, tree):
        return f"foreach({self.visit(tree.children[0])} in {self.visit(tree.children[1])})\n{self.visit(tree.children[2])}\n"

    def del_key(self, tree):
        return f"del {tree.children[0].value}[{self.visit(tree.children[1])}]"

    def parameters(self, tree):
        return ", ".join((self.visit(v) for v in tree.children))

    def ret(self, tree):
        return f"return {self.visit(tree.children[0])};"

    def main(self, tree):
        return f"main({self.visit(tree.children[0])}) {self.visit(tree.children[1])}\n"
