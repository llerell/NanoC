from lark import Tree

class PrettyPrinter:

    def visit(self, node):
        # Cas d'une feuille
        if not isinstance(node, Tree):
            return node
            
        rule = node.data
        methode = getattr(self, rule, None) # plus simple qu'une série de if/else
        
        if methode is None:
            raise NotImplementedError(f"il n'y a pas de méthode pour la rêgle de grammaire '{rule}'.")
            
        return methode(node)

    # EXPRESSIONS
    def entier(self, tree):
        return tree.children[0].value

    def double(self, tree):
        return tree.children[0].value

    def chaine(self, tree):
        return tree.children[0].value
    
    def caractere(self, tree):
        return tree.children[0].value

    def binaire(self, tree):
        return f"{self.visit(tree.children[0])} {tree.children[1].value} {self.visit(tree.children[2])}"

    def variable(self, tree):
        return tree.children[0].value
    
    def conversion(self, tree):
        return f"{tree.children[0].value}({self.visit(tree.children[1])})"
    
    def non_logique(self, tree):
        return f"!{self.visit(tree.children[0])}"

    def atoi(self, tree):
        return f"atoi({self.visit(tree.children[0])})"

    def length(self, tree):
        return f"len({self.visit(tree.children[0])})"

    def charat(self, tree):
        return f"charat({self.visit(tree.children[0])}, {self.visit(tree.children[1])})"

    # COMMANDES

    def assignation(self, tree):
        return f"{tree.children[0].value} = {self.visit(tree.children[1])};"

    def nop(self, tree):
        return "pass"

    def print(self, tree):
        return f"print({self.visit(tree.children[0])});"

    def sequence(self, tree):
        return f"{self.visit(tree.children[0])}\n{self.visit(tree.children[1])}"
    
    def block_while(self, tree):
        return f"while ({self.visit(tree.children[0])}) {{\n{self.visit(tree.children[1])}\n}}"
    
    def block_if(self, tree):
        return f"if ({self.visit(tree.children[0])}) {{\n{self.visit(tree.children[1])}\n}}"

    def liste_vars(self, tree):
        return ", ".join((f"{v.children[0].value} {v.children[1].value}" for v in tree.children))

    def main(self, tree):
        return f"main({self.visit(tree.children[0])}) {{\n{self.visit(tree.children[1])}\n    return {self.visit(tree.children[2])};\n}}"

