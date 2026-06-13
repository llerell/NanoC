from lark import Tree, Token


class Type:
    pass


class PrimitiveType(Type):
    def __init__(self, name: str):
        self.name = name  # "int", "double", "str"

    def __eq__(self, other):
        return isinstance(other, PrimitiveType) and self.name == other.name

    def __str__(self):
        return self.name


class DictType(Type):
    def __init__(self, key_type: PrimitiveType, value_type: Type):
        self.key_type = key_type
        self.value_type = value_type  # Peut être un PrimitiveType ou un autre DictType

    def __eq__(self, other):
        return (
            isinstance(other, DictType)
            and self.key_type == other.key_type
            and self.value_type == other.value_type
        )

    def __str__(self):
        return f"dict<{self.key_type},{self.value_type}>"

TYPE_INT = PrimitiveType("int")
TYPE_DOUBLE = PrimitiveType("double")
TYPE_STR = PrimitiveType("str")

class Scope:
    def __init__(self, parent: Scope):
        self.variables: dict[str, tuple[Type, int]] = {}
        self.parent = parent

    def dcl(self, nom: str, type_var: Type, offset: int):
        """Déclare une variable dans le scope courant"""
        if nom in self.variables:
            raise NameError(
                f"Erreur : La variable '{nom}' est déjà déclarée dans ce bloc."
            )
        self.variables[nom] = (type_var, offset)

    def lookup(self, nom: str) -> tuple[Type, int]:
        """Cherche une variable ici, ou remonte chez les parents"""
        if nom in self.variables:
            return self.variables[nom]
        return self.parent.lookup(nom)


class MainScope(Scope):
    def __init__(self):
        self.variables = {}

    def lookup(self, nom: str) -> tuple[Type, int]:
        if nom in self.variables:
            return self.variables[nom]
        raise NameError(f"Erreur : La variable '{nom}' n'est pas déclarée.")


class TypeChecker:

    def __init__(self):
        self.current_scope: Scope = MainScope()  # Le scope global de main
        self.node_types = {}
        self.var_offsets = {}
        self.current_offset = 8
        self.stack_size = 0

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

    ### EXPRESSIONS

    def entier(self, tree):
        self.node_types[tree] = TYPE_INT
        return TYPE_INT

    def double(self, tree):
        self.node_types[tree] = TYPE_DOUBLE
        return TYPE_DOUBLE

    def chaine(self, tree):
        self.node_types[tree] = TYPE_STR
        return TYPE_STR

    def nested_type(self, tree):
        """Transforme le nœud de grammaire 'nested_type' en objet Type."""

        if len(tree.children) == 1:
            return PrimitiveType(tree.children[0].value)

        key_type = PrimitiveType(tree.children[1].value)
        value_type = self.visit(tree.children[2])
        return DictType(key_type, value_type)

    def binaire(self, tree):
        type_g = self.visit(tree.children[0])
        op = tree.children[1].value
        type_d = self.visit(tree.children[2])

        if type_g == type_d:
            self.node_types[tree] = type_g
            return type_g

        if type_g == TYPE_INT and type_d == TYPE_DOUBLE:
            noeud_cast = Tree("conversion", [Token("TYPE", "double"), tree.children[0]])
            tree.children[0] = noeud_cast

            self.node_types[noeud_cast] = TYPE_DOUBLE
            self.node_types[tree] = TYPE_DOUBLE
            return TYPE_DOUBLE

        if type_g == TYPE_DOUBLE and type_d == TYPE_INT:
            noeud_cast = Tree("conversion", [Token("TYPE", "double"), tree.children[2]])
            tree.children[2] = noeud_cast

            self.node_types[noeud_cast] = TYPE_DOUBLE
            self.node_types[tree] = TYPE_DOUBLE
            return TYPE_DOUBLE

        raise TypeError(f"Opération {op} impossible entre {type_g} et {type_d}")

    def variable(self, tree):
        """Utilisation d'une variable (ex: rax = x)"""
        nom_var = tree.children[0].value

        type_var, offset = self.current_scope.lookup(nom_var)

        self.node_types[tree] = type_var
        self.var_offsets[tree] = offset
        return type_var

    def dict_access(self, tree):
        nom_var = tree.children[0].value
        type_expr = self.visit(tree.children[1])

        type_var, offset = self.current_scope.lookup(nom_var)

        if not isinstance(type_var, DictType):
            raise TypeError(f"La variable '{nom_var}' n'est pas un dictionnaire.")

        if type_var.key_type != type_expr:
            raise TypeError(
                f"La clé doit être de type {type_var.key_type.name}, pas {type_expr.name}"
            )

        self.node_types[tree] = type_var.value_type
        self.var_offsets[tree] = offset

        return type_var.value_type

    def dict_literal(self, tree):

        if len(tree.children) == 0:
            return None

        type_cle = self.visit(tree.children[0])
        type_valeur = self.visit(tree.children[1])

        for i in range(2, len(tree.children), 2):
            key = self.visit(tree.children[i])
            val = self.visit(tree.children[i + 1])
            if key != type_cle:
                raise TypeError(f"La clé doit être de type {type_cle}, pas {key}")
            if val != type_valeur:
                raise TypeError(f"La valeur doit être de type {type_valeur}, pas {val}")

        dict_type = DictType(type_cle, type_valeur)
        self.node_types[tree] = dict_type
        return dict_type

    def conversion(self, tree):
        type_cible = tree.children[0].value
        self.node_types[tree] = type_cible
        type_src = self.visit(tree.children[1])

        return type_cible

    def non_logique(self, tree):
        type_expr = self.visit(tree.children[0])
        if type_expr != TYPE_INT:
            raise TypeError("Le non logique ne s'applique qu'aux variables de type int")
        self.node_types[tree] = TYPE_INT
        return TYPE_INT

    def parenthese(self, tree):
        type_expr = self.visit(tree.children[0])
        self.node_types[tree] = type_expr
        return type_expr

    def atoi(self, tree):
        type_expr = self.visit(tree.children[0])
        if type_expr != TYPE_STR:
            raise TypeError("L'atoi ne s'applique qu'aux variables de type str")
        self.node_types[tree] = TYPE_INT
        return TYPE_INT

    def length(self, tree):
        type_expr = self.visit(tree.children[0])
        if type_expr != TYPE_STR:
            raise TypeError("La longueur ne s'applique qu'aux variables de type str")
        self.node_types[tree] = TYPE_INT
        return TYPE_INT

    def charat(self, tree):
        type_expr = self.visit(tree.children[0])
        if type_expr != TYPE_STR:
            raise TypeError("Le charat ne s'applique qu'aux variables de type str")
        self.node_types[tree] = TYPE_INT
        return TYPE_INT

    ### COMMANDES

    def decl_assignation(self, tree):
        """Exemple pour : int x = 5;"""
        decl_node = tree.children[0]
        type_var = self.visit(decl_node.children[0])
        nom_var = decl_node.children[1].value

        offset = self.current_offset
        self.current_offset += 8

        self.current_scope.dcl(nom_var, type_var, offset)
        type_expr = self.visit(tree.children[1])

        if type_expr is None:
            type_expr = type_var
            self.node_types[tree.children[1]] = type_expr

        if type_var != type_expr:
            raise TypeError(
                f"Impossible d'assigner {type_expr} à {nom_var} ({type_var})"
            )

        self.var_offsets[tree] = offset
        self.node_types[tree] = type_expr

        return type_var

    def assignation(self, tree):
        nom_var = tree.children[0].value
        lhs_type, offset = self.current_scope.lookup(nom_var)

        rhs_type = self.visit(tree.children[1])
        self.var_offsets[tree] = offset

        if rhs_type is None:
            rhs_type = lhs_type
            self.node_types[tree.children[1]] = rhs_type

        if lhs_type != rhs_type:
            raise TypeError(f"Impossible d'assigner {rhs_type} à {lhs_type}")

    def assignation_dict(self, tree):
        nom_var = tree.children[0].value
        lhs_type, offset = self.current_scope.lookup(nom_var)
        key_type = self.visit(tree.children[1])
        rhs_type = self.visit(tree.children[2])

        if not isinstance(lhs_type, DictType):
            raise TypeError(f"'{nom_var}' n'est pas un dictionnaire.")

        if lhs_type.key_type != key_type:
            raise TypeError(f"Type de clé invalide. Attendu: {lhs_type.key_type.name}")

        if lhs_type.value_type != rhs_type:
            raise TypeError(
                f"Type de valeur invalide. Attendu: {lhs_type.value_type.name if isinstance(lhs_type.value_type, PrimitiveType) else 'dictionnaire'}"
            )

        self.var_offsets[tree] = offset
        self.node_types[tree] = lhs_type

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
        if type_condition != TYPE_INT:
            raise TypeError("La condition n'est pas un booléen")
        self.visit(tree.children[1])

    def block_if(self, tree):
        """Gestion d'un bloc 'if' ouvrant des accolades {}"""
        type_condition = self.visit(tree.children[0])
        if type_condition != TYPE_INT:
            raise TypeError("La condition n'est pas un booléen")
        self.visit(tree.children[1])

    def foreach(self, tree):
        dict_name = tree.children[1].value
        type_dict, dict_offset = self.current_scope.lookup(dict_name)

        if not isinstance(type_dict, DictType):
            raise TypeError(f"La variable doit être un dictionnaire (reçu {type_dict})")

        # 2. Création d'un NOUVEAU scope pour isoler les variables de la boucle
        self.current_scope = Scope(self.current_scope)

        # 3. Allocation de la variable locale pour la clé
        key_name = tree.children[0].value
        key_offset = self.current_offset
        self.current_offset += 8
        self.current_scope.dcl(key_name, type_dict.key_type, key_offset)

        # 4. Allocation d'une variable CACHÉE pour le compteur (index)
        index_offset = self.current_offset
        self.current_offset += 8
        
        # 5. On emballe toutes les métadonnées (adresses) pour le CodeGenerator
        self.var_offsets[tree] = {
            "key_offset": key_offset,
            "index_offset": index_offset,
            "dict_offset": dict_offset
        }
        self.node_types[tree] = type_dict
        
        # 6. Visite du bloc d'instructions
        self.visit(tree.children[2])
        
        # 7. Sortie du scope (destruction des variables de boucle)
        self.current_scope = self.current_scope.parent
    
    def del_key(self, tree):
        dict_name = tree.children[0].value
        dict_type, dict_offset = self.current_scope.lookup(dict_name)

        if not isinstance(dict_type, DictType):
            raise TypeError(f"La variable doit être un dictionnaire (reçu {dict_type})")

        key_type = self.visit(tree.children[1])
        if key_type != dict_type.key_type:
            raise TypeError(f"Type de clé invalide. Attendu: {dict_type.key_type.name}")

        self.var_offsets[tree] = dict_offset
        self.node_types[tree] = dict_type
        
    def parameters(self, tree):
        # Pour les arguments de la fonction main
        for decl in tree.children:
            type_var = decl.children[0].value
            nom_var = decl.children[1].value

            offset = self.current_offset
            self.current_offset += 8

            self.current_scope.dcl(nom_var, type_var, offset)
            self.var_offsets[decl] = offset

    def ret(self, tree):
        self.visit(tree.children[0])

    def main(self, tree):
        self.visit(tree.children[0])
        self.visit(tree.children[1])

        # Calcul de la taille de pile totale à la fin de l'analyse
        self.stack_size = self.current_offset - 8
        # Alignement strict x86_64 sur 16 octets
        if self.stack_size % 16 != 0:
            self.stack_size += 16 - (self.stack_size % 16)
