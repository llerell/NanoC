from lark import Tree, Token

class Scope:
    def __init__(self, parent:Scope):
        self.variables = {}  # { 'nom': 'type' } local à ce bloc
        self.parent = parent # Pointeur vers le scope supérieur (None pour le global)

    def dcl(self, nom: str, type_var: str):
        """Déclare une variable dans le scope courant"""
        if nom in self.variables:
            raise NameError(f"Erreur : La variable '{nom}' est déjà déclarée dans ce bloc.")
        self.variables[nom] = type_var

    def lookup(self, nom: str) -> str:
        """Cherche une variable ici, ou remonte chez les parents"""
        if nom in self.variables:
            return self.variables[nom]
        if self.parent is not None:
            return self.parent.lookup(nom)
        raise NameError(f"Erreur : La variable '{nom}' n'est pas déclarée.")

class MainScope(Scope):
    def __init__(self):
        self.variables = {}


class TypeChecker:

    def __init__(self):
        self.current_scope: Scope = MainScope() # Le scope global de main
        self.node_types = {}
        self.toutes_les_variables = set()

    def visit(self, node):
        # Cas d'une feuille
        if not isinstance(node, Tree):
            return node
            
        rule = node.data
        methode = getattr(self, rule, None) # plus simple qu'une série de if/else
        
        if methode is None:
            raise NotImplementedError(f"il n'y a pas de méthode pour la rêgle de grammaire '{rule}'.")
            
        return methode(node)

    ### EXPRESSIONS

    def entier(self, tree):
        self.node_types[tree] = "int"
        return "int"

    def double(self, tree):
        self.node_types[tree] = "double"
        return "double"

    def chaine(self, tree):
        self.node_types[tree] = "str"
        return "str"
    
    def caractere(self, tree):
        self.node_types[tree] = "int"
        return "int"

    def binaire(self, tree):
        type_g = self.visit(tree.children[0])
        op = tree.children[1].value
        type_d = self.visit(tree.children[2])

        if type_g == type_d:
            self.node_types[tree] = type_g
            return type_g


        if type_g == "int" and type_d == "double":
            # On crée un faux nœud de conversion pour le fils gauche : double(expression)
            noeud_cast = Tree('conversion', [Token('TYPE', 'double'), tree.children[0]])
            # On remplace le fils gauche dans l'arbre par ce nouveau nœud
            tree.children[0] = noeud_cast
            
            self.node_types[noeud_cast] = "double"
            self.node_types[tree] = "double"
            return "double"

        # Cas 3 : double + int -> On promeut le int droit en double
        if type_g == "double" and type_d == "int":
            noeud_cast = Tree('conversion', [Token('TYPE', 'double'), tree.children[2]])
            tree.children[2] = noeud_cast
            
            self.node_types[noeud_cast] = "double"
            self.node_types[tree] = "double"
            return "double"

        # Autres cas non supportés (ex: str + int)
        raise TypeError(f"Opération {op} impossible entre {type_g} et {type_d}")

    def variable(self, tree):
        """Utilisation d'une variable (ex: rax = x)"""
        nom_var = tree.children[0].value
        # lookup va automatiquement chercher dans le scope courant, ou remonter si besoin
        type_var = self.current_scope.lookup(nom_var)
        
        self.node_types[tree] = type_var
        return type_var

    def conversion(self, tree):
        type_cible = tree.children[0].value
        self.node_types[tree] = type_cible
        type_src = self.visit(tree.children[1])
        
        return type_cible
    
    def non_logique(self, tree):
        type_expr = self.visit(tree.children[0])
        if type_expr != "int":
            raise TypeError("Le non logique ne s'applique qu'aux variables de type int")
        self.node_types[tree] = "int"
        return "int"

    def atoi(self, tree):
        type_expr = self.visit(tree.children[0])
        if type_expr != "str":
            raise TypeError("L'atoi ne s'applique qu'aux variables de type str")
        self.node_types[tree] = "int"
        return "int"

    def length(self, tree):
        type_expr = self.visit(tree.children[0])
        if type_expr != "str":
            raise TypeError("La longueur ne s'applique qu'aux variables de type str")
        self.node_types[tree] = "int"
        return "int"

    def charat(self, tree):
        type_expr = self.visit(tree.children[0])
        if type_expr != "str":
            raise TypeError("Le charat ne s'applique qu'aux variables de type str")
        self.node_types[tree] = "int"
        return "int"

    ### COMMANDES

    def decl_assignation(self, tree):
        """Exemple pour : int x = 5;"""
        type_var = tree.children[0].value
        nom_var = tree.children[1].value
        
        # 1. On enregistre la variable dans le scope actuel
        self.current_scope.dcl(nom_var, type_var)
        self.toutes_les_variables.add(nom_var) # On s'en souvient pour plus tard
        
        # 2. On vérifie le type de l'expression à droite
        type_expr = self.visit(tree.children[2])
        if type_var != type_expr:
            raise TypeError(f"Impossible d'assigner {type_expr} à {nom_var} ({type_var})")
            
        return type_var

    def assignation(self, tree):
        lhs_type = self.current_scope.lookup(tree.children[0].value)
        rhs_type = self.visit(tree.children[1])
        if lhs_type != rhs_type:
            raise TypeError(f"Impossible d'assigner {rhs_type} à {lhs_type}")
        
    def nop(self, tree):
        pass

    def print(self, tree):
        type_expr = self.visit(tree.children[0])

    def bloc(self, tree):
        # --- ENTRÉE DE SCOPE ---
        self.current_scope = Scope(parent=self.current_scope)
        
        for child in tree.children:
            self.visit(child)
        
        # --- SORTIE DE SCOPE ---
        self.current_scope = self.current_scope.parent
    
    def block_while(self, tree):
        """Gestion d'un bloc 'while' ouvrant des accolades {}"""
        type_condition = self.visit(tree.children[0])
        if type_condition != "int":
            raise TypeError("La condition n'est pas un booléen")
        self.visit(tree.children[1])
    
    def block_if(self, tree):
        """Gestion d'un bloc 'if' ouvrant des accolades {}"""
        type_condition = self.visit(tree.children[0])
        if type_condition != "int":
            raise TypeError("La condition n'est pas un booléen")
        self.visit(tree.children[1])
    
    def liste_vars(self, tree):
        for decl in tree.children:
            type_var = decl.children[0].value
            nom_var = decl.children[1].value
            self.current_scope.dcl(nom_var, type_var)
            self.toutes_les_variables.add(nom_var)
    
    def ret(self, tree):
        self.visit(tree.children[0])

    def main(self, tree):

        self.visit(tree.children[0])
        self.visit(tree.children[1])
