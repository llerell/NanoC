from lark import Tree
from TypeChecker import PrimitiveType, DictType, Type


class CodeGenerator:

    def __init__(
        self,
        node_types: dict[Tree, Type],
        var_offsets: dict[Tree, int|dict[str, int]],
        stack_size: int,
    ):
        self.compteur = iter(range(1_000_000))
        self.constantes = {}
        self.node_types = node_types
        self.var_offsets = var_offsets
        self.stack_size = stack_size

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

    # HELPERS

    def _push_type(self, ast_type):
        """Génère l'assembleur pour empiler une valeur selon son type."""
        if ast_type == PrimitiveType("double"):
            return "sub rsp, 8\nmovsd [rsp], xmm0"
        return "push rax"

    def _pop_type(self, ast_type, target_reg):
        """Génère l'assembleur pour dépiler une valeur vers un registre cible."""
        if ast_type == PrimitiveType("double"):
            # Même pour les flottants, set_in_dict attend les bits dans les registres généraux (rsi, rdx)
            return f"movsd xmm0, [rsp]\nadd rsp, 8\nmovq {target_reg}, xmm0"
        return f"pop {target_reg}"

    def _mov_type(self, ast_type, dest, src):
        """
        Génère l'instruction de déplacement appropriée selon le type de donnée.
        """
        if ast_type == PrimitiveType("double"):
            return f"movsd {dest}, {src}"
        return f"mov {dest}, {src}"

    def _get_const_label(self, type_lit, valeur):
        """
        Renvoie le label de la constante ; si celle-ci n'est pas encore définie,
        on l'ajoute à la liste des constantes.
        """
        if (type_lit, valeur) not in self.constantes:
            label = f"const_{len(self.constantes)}"
            self.constantes[(type_lit, valeur)] = label
        return self.constantes[(type_lit, valeur)]

    # EXPRESSIONS

    def entier(self, tree):
        """
        Un entier litéral
        """
        return f"mov rax, {tree.children[0].value}\n"

    def double(self, tree):
        """
        Un double litéral
        """
        label = self._get_const_label(tree.data, tree.children[0].value)
        return f"movsd xmm0, [{label}]\n"

    def chaine(self, tree):
        """
        Une chaîne de caractères litérale
        """
        label = self._get_const_label(tree.data, tree.children[0].value)
        return f"mov rax, {label}\n"

    def nested_type(self, tree):
        raise NotImplementedError("full_type non implémenté")

    def binaire(self, tree):
        type_g = self.node_types[tree.children[0]]
        op = tree.children[1].value
        type_d = self.node_types[tree.children[2]]
        asm_g = self.visit(tree.children[0])
        asm_d = self.visit(tree.children[2])

        if type_g == type_d == PrimitiveType("str") and op == "+":
            return self._concat(asm_g, asm_d)

        if type_g == type_d == PrimitiveType("int"):
            base_asm = f"""{asm_d}
                                sub rsp, 16
                                mov [rsp], rax
                                {asm_g}
                                mov rbx, [rsp]
                                add rsp, 16
                            """
            opbin = {
                "+": "add",
                "-": "sub",
                "*": "imul",
                "&&": "and",
                "&": "and",
                "||": "or",
                "|": "or",
                "^": "xor",
            }
            opcomp = {
                "<": "setl",
                ">": "setg",
                "<=": "setle",
                ">=": "setge",
                "==": "sete",
                "!=": "setne",
            }

            if op == "/":
                return base_asm + "cqo\nidiv rbx\n"
            if op == "%":
                return base_asm + "cqo\nidiv rbx\nmov rax, rdx\n"

            if op in opbin:
                return base_asm + f"{opbin[op]} rax, rbx\n"
            if op in opcomp:
                return base_asm + f"cmp rax, rbx\n{opcomp[op]} al\nmovzx rax, al\n"

        elif type_g == type_d == PrimitiveType("double"):
            # Attention, pour empiler xmm0, il faut utiliser la pile manuellement (rsp)
            base_asm = f"""{asm_d}
                                sub rsp, 16
                                movsd [rsp], xmm0
                                {asm_g}
                                movsd xmm1, [rsp]
                                add rsp, 16
                            """
            opbin = {"+": "addsd", "-": "subsd", "*": "mulsd", "/": "divsd"}
            opcomp = {
                "<": "setb",
                ">": "seta",
                "<=": "setbe",
                ">=": "setae",
                "==": "sete",
                "!=": "setne",
            }

            if op in opbin:
                return base_asm + f"{opbin[op]} xmm0, xmm1\n"
            if op in opcomp:
                return (
                    base_asm + f"ucomisd xmm0, xmm1\n{opcomp[op]} al\nmovzx rax, al\n"
                )

        raise TypeError(
            f"Incompatibilité de types: impossible de faire '{type_g} {op} {type_d}'"
        )

    def variable(self, tree):
        type_var = self.node_types[tree]
        offset = self.var_offsets[tree]

        if type_var == PrimitiveType("double"):
            return f"movsd xmm0, [rbp - {offset}]\n"
        return f"mov rax, [rbp - {offset}]\n"

    def dict_access(self, tree):
        key_asm = self.visit(tree.children[1])

        offset = self.var_offsets[tree]

        return f"""{key_asm}
                    mov rsi, rax
                    mov rdi, [rbp - {offset}]
                    call get_from_dict
                """

    def dict_literal(self, tree):
        dict_type = self.node_types[tree]
        assert isinstance(dict_type, DictType)

        key_type = dict_type.key_type
        val_type = dict_type.value_type

        # Initialisation de l'adresse de tête du dictionnaire (NULL) sur la pile
        asm = ["xor rax, rax", "push rax"]

        for i in range(0, len(tree.children) - 1, 2):
            key_node = tree.children[i]
            val_node = tree.children[i + 1]

            # 1. Évaluer et empiler la valeur
            asm.append(self.visit(val_node))
            asm.append(self._push_type(val_type))

            # 2. Évaluer et empiler la clé
            asm.append(self.visit(key_node))
            asm.append(self._push_type(key_type))

            # 3. Dépiler dans les registres d'arguments (rsi, rdx)
            asm.append(self._pop_type(key_type, "rsi"))
            asm.append(self._pop_type(val_type, "rdx"))

            # 4. Insertion dans le dictionnaire
            # L'adresse de la tête (le NULL initial ou la tête mise à jour) est pointée par rsp
            asm.append("lea rdi, [rsp]")
            asm.append("call set_in_dict")

        # À la fin, on dépile l'adresse de la tête du dictionnaire dans rax
        # (C'est ce qui sera affecté à la variable lors du `decl_assignation`)
        asm.append("pop rax\n")

        return "\n".join(asm)

    def conversion(self, tree):
        type_cible = tree.children[0].value
        type_src = self.node_types[tree.children[1]]
        asm_src = self.visit(tree.children[1])

        if type_src == type_cible:
            return asm_src

        if type_cible == PrimitiveType("double") and type_src == PrimitiveType("int"):
            return asm_src + "cvtsi2sd xmm0, rax\n"

        if type_cible == PrimitiveType("int") and type_src == PrimitiveType("double"):
            # arrondi au plus proche
            return asm_src + "cvtsd2si rax, xmm0\n"

        raise TypeError(f"Conversion impossible : {type_src} vers {type_cible}")

    def non_logique(self, tree):
        asm_expr = self.visit(tree.children[0])

        return f"""{asm_expr}
                    cmp rax, 0
                    sete al
                    movzx rax, al
                """

    def parenthese(self, tree):
        return self.visit(tree.children[0])

    def atoi(self, tree):
        return f"""{self.visit(tree.children[0])}
                    mov rdi, rax
                    call atoi
                """

    def length(self, tree):
        return f"""{self.visit(tree.children[0])}
                    mov rdi, rax
                    call strlen
                """

    def charat(self, tree):
        str_asm = self.visit(tree.children[0])
        idx_asm = self.visit(tree.children[1])
        # On évalue d'abord l'index qu'on pousse sur la pile, puis l'adresse de la chaîne
        return (
            idx_asm + "push rax\n" + str_asm + "pop rbx\nmovzx rax, byte [rax + rbx]\n"
        )

    def _concat(self, asm_g, asm_d):
        # TODO
        raise NotImplementedError("concaténation de chaînes non implémentée")

    # COMMANDES

    def assignation(self, tree):
        type_var = self.node_types[tree.children[1]]
        asm_expr = self.visit(tree.children[1])
        offset = self.var_offsets[tree]

        if type_var == PrimitiveType("double"):
            return f"{asm_expr}movsd [rbp - {offset}], xmm0\n"
        return f"{asm_expr}mov [rbp - {offset}], rax\n"

    def decl_assignation(self, tree):
        # Gère l'écriture lors d'une déclaration à la volée avec assignation (ex: int y = 10;)
        asm_expr = self.visit(tree.children[1])  # L'expression est bien à l'index 1

        type_var = self.node_types[tree]
        offset = self.var_offsets[tree]

        if type_var == PrimitiveType("double"):
            return f"{asm_expr}movsd [rbp - {offset}], xmm0\n"
        return f"{asm_expr}mov [rbp - {offset}], rax\n"

    def assignation_dict(self, tree):
        offset = self.var_offsets[tree]

        key_node = tree.children[1]
        val_node = tree.children[2]

        # Récupération des types définis par le TypeChecker
        key_type = self.node_types[key_node]
        val_type = self.node_types[val_node]

        asm = []

        # 1. Évaluer et sauvegarder la valeur sur la pile
        asm.append(self.visit(val_node))
        asm.append(self._push_type(val_type))

        # 2. Évaluer et sauvegarder la clé sur la pile
        asm.append(self.visit(key_node))
        asm.append(self._push_type(key_type))

        # 3. Préparer les registres pour l'appel à set_in_dict
        asm.append(
            f"lea rdi, [rbp - {offset}]"
        )  # rdi = adresse de la variable dictionnaire
        asm.append(
            self._pop_type(key_type, "rsi")
        )  # rsi = la clé qu'on vient de dépiler
        asm.append(
            self._pop_type(val_type, "rdx")
        )  # rdx = la valeur qu'on dépile ensuite

        # 4. Appel de la fonction de la bibliothèque standard
        asm.append("call set_in_dict\n")

        return "\n".join(asm)

    def nop(self, tree):
        return "nop\n"

    def print(self, tree):

        type_expr = self.node_types[tree.children[0]]
        asm_expr = self.visit(tree.children[0])

        if type_expr == PrimitiveType("int"):
            return f"""{asm_expr}
                        mov rdi, format_entier
                        mov rsi, rax
                        xor rax, rax
                        call printf
                        """

        elif type_expr == PrimitiveType("double"):
            return f"""{asm_expr}
                        mov rdi, format_flottant
                        mov rax, 1
                        call printf
                    """
        elif type_expr == PrimitiveType("str"):
            return f"""{asm_expr}
                        mov rdi, format_chaine
                        mov rsi, rax
                        xor rax, rax
                        call printf
                    """

        raise TypeError(f"Impossible d'imprimer le type {type_expr}")

    def bloc(self, tree):
        return "\n".join(self.visit(child) for child in tree.children)

    def block_while(self, tree):
        test = self.visit(tree.children[0])
        cmd = self.visit(tree.children[1])

        cpt = next(self.compteur)
        return f"""debut_{cpt}: {test}
                    cmp rax, 0
                    jz fin_{cpt}
                    {cmd}
                    jmp debut_{cpt}
                    fin_{cpt}:
                    """

    def block_if(self, tree):
        test = self.visit(tree.children[0])
        cmd = self.visit(tree.children[1])

        cpt = next(self.compteur)
        return f"""{test}
                    cmp rax, 0
                    jz fin_{cpt}
                    {cmd}
                    fin_{cpt}:
                    """
    
    def foreach(self, tree):
        # 1. Récupération des adresses et types calculés par le TypeChecker
        offsets = self.var_offsets[tree]
        assert isinstance(offsets, dict)
        key_offset = offsets["key_offset"]
        index_offset = offsets["index_offset"]
        dict_offset = offsets["dict_offset"]
        
        dict_type = self.node_types[tree]
        assert isinstance(dict_type, DictType)
        key_type = dict_type.key_type
        
        # Étiquettes uniques pour la boucle
        label_start = f".foreach_start_{next(self.compteur)}"
        label_end = f".foreach_end_{next(self.compteur)}"
        
        asm = []
        
        # 2. Initialiser l'index caché à 0 en mémoire
        asm.append(f"mov qword [rbp - {index_offset}], 0")
        
        asm.append(f"{label_start}:")
        
        # 3. Condition de sortie (index >= taille)
        asm.append(f"mov rdi, [rbp - {dict_offset}]")
        asm.append("call dict_get_size")              # rax = taille du dico
        asm.append(f"mov rcx, [rbp - {index_offset}]") # rcx = index courant
        asm.append("cmp rcx, rax")
        asm.append(f"jge {label_end}")                # Si index >= taille, on quitte
        
        # 4. Récupération de la clé à l'index courant
        asm.append(f"mov rdi, [rbp - {dict_offset}]")
        asm.append(f"mov rsi, [rbp - {index_offset}]")
        asm.append("call dict_get_key_by_index")      # rax = la clé
        
        # 5. Affectation de la clé retournée dans la variable de la boucle
        if key_type == PrimitiveType("double"):
            # Si c'est un double, dict_get_key a copié les bits dans rax.
            # On les bascule dans xmm0, puis on les sauvegarde en mémoire.
            asm.append("movq xmm0, rax")
            asm.append(f"movsd [rbp - {key_offset}], xmm0")
        else:
            asm.append(f"mov [rbp - {key_offset}], rax")
            
        # 6. Exécution du bloc de commandes du foreach
        asm.append(self.visit(tree.children[2]))
        
        # 7. Incrémentation de l'index et rebouclage
        asm.append(f"inc qword [rbp - {index_offset}]")
        asm.append(f"jmp {label_start}")
        
        asm.append(f"{label_end}:")
        
        return "\n".join(asm) + "\n"

    def del_key(self, tree):
        dict_offset = self.var_offsets[tree]
        dict_type = self.node_types[tree]
        assert isinstance(dict_type, DictType)
        key_type = dict_type.key_type
        
        res_asm = [self.visit(tree.children[1])]

        res_asm.append(self._push_type(key_type))
        res_asm.append(f"lea rdi, [rbp - {dict_offset}]")
        res_asm.append(self._pop_type(key_type, "rsi"))
        res_asm.append("call delete_from_dict")

        return "\n".join(res_asm) + "\n"

    def parameters(self, tree):
        res = []
        for i in range(len(tree.children)):
            decl_node = tree.children[i]
            type_var = decl_node.children[0].value
            offset = self.var_offsets[decl_node]

            base = f"""mov rdi, [argv]
                        mov rdi, [rdi + {(i+1)*8}]
                        """

            if type_var == PrimitiveType("int"):
                res.append(base + f"call atoi\nmov [rbp - {offset}], rax")
            elif type_var == PrimitiveType("double"):
                res.append(base + f"call atof\nmovsd [rbp - {offset}], xmm0")
            elif type_var == PrimitiveType("str"):
                res.append(base + f"mov [rbp - {offset}], rdi")

        return "\n".join(res) + "\n"

    def _decls_vars(self, tree):
        return "\n".join(
            f"{tree.children[i].children[1].value}: dq 0"
            for i in range(len(tree.children))
        )

    def ret(self, tree):
        asm_expr = self.visit(tree.children[0])
        return f"""{asm_expr}
                    jmp end_main
                """

    def main(self, tree):

        parameters = self.visit(tree.children[0])
        commands = self.visit(tree.children[1])

        declaration = self._decls_vars(tree.children[0])

        # Génération des constantes (const_float_0: dq 3.14)
        asm_consts = "\n".join(
            f"{label}: dq {valeur[1]}" for valeur, label in self.constantes.items()
        )

        squelette = open("squelette.asm").read()
        dict_squelette = open("dict_squelette.asm").read()

        # Allocation globale de la pile pour toutes les variables du programme
        allocation_stack = (
            f"sub rsp, {self.stack_size}\n" if self.stack_size > 0 else ""
        )

        squelette = squelette.replace("INIT_VARS", allocation_stack + parameters)
        squelette = squelette.replace("DICT", dict_squelette)
        squelette = squelette.replace("CONSTANTES", asm_consts)
        squelette = squelette.replace("COMMAND", commands)
        squelette = squelette.replace("  ", "")

        return squelette
