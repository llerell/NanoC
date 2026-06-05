from lark import Tree


class CodeGenerator:

    def __init__(self, node_types: dict[Tree, str], all_variables: set[str]):
        self.compteur = iter(range(1_000_000))
        self.constantes = {}
        self.node_types = node_types
        self.all_variables = all_variables

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
        return f"mov rax, {tree.children[0].value}\n"

    def double(self, tree):
        type_lit = tree.data
        valeur = tree.children[0].value

        # vérification de la présence de la constante
        if (type_lit, valeur) not in self.constantes:
            label = f"const_{len(self.constantes)}"
            self.constantes[(type_lit, valeur)] = label
        else:
            label = self.constantes[(type_lit, valeur)]

        return f"movsd xmm0, [{label}]\n"

    def chaine(self, tree):
        return tree.children[0].value

    def caractere(self, tree):
        return f"mov rax, {tree.children[0].value}\n"

    def binaire(self, tree):
        type_g = self.node_types[tree.children[0]]
        op = tree.children[1].value
        type_d = self.node_types[tree.children[2]]
        asm_g = self.visit(tree.children[0])
        asm_d = self.visit(tree.children[2])

        if type_g == "str" and type_d == "str" and op == "+":
            return self._concat(asm_g, asm_d)

        if type_g == type_d == "int":
            base_asm = f"{asm_d}push rax\n{asm_g}pop rbx\n"
            opbin = {
                "+": "add",
                "-": "sub",
                "*": "imul",
                "&": "and",
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
                return (base_asm + f"cmp rax, rbx\n{opcomp[op]} al\nmovzx rax, al\n",)

        elif type_g == type_d == "double":
            # Attention, pour empiler xmm0, il faut utiliser la pile manuellement (rsp)
            base_asm = f"""{asm_d}
                                sub rsp, 8
                                movsd [rsp], xmm0
                                {asm_g}
                                movsd xmm1, [rsp]
                                add rsp, 8
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
                    base_asm + f"ucomisd xmm0, xmm1\n{opcomp[op]} al\nmovzx rax, al\n",
                )

        raise TypeError(
            f"Incompatibilité de types: impossible de faire '{type_g} {op} {type_d}'"
        )

    def variable(self, tree):
        nom = tree.children[0].value
        type_var = self.node_types[tree]

        if type_var == "int":
            return f"mov rax, [{nom}]\n"
        elif type_var == "double":
            return f"movsd xmm0, [{nom}]\n"
        elif type_var == "str":
            return f"mov rax, [{nom}]\n"

    def conversion(self, tree):
        type_cible = tree.children[0].value
        type_src = self.node_types[tree.children[1]]
        asm_src = self.visit(tree.children[1])

        if type_src == type_cible:
            return asm_src

        if type_cible == "double" and type_src == "int":
            return asm_src + "cvtsi2sd xmm0, rax\n"

        if type_cible == "int" and type_src == "double":
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
        lhs = self.visit(tree.children[0])

        type_var = self.node_types[tree.children[1]]
        asm_expr = self.visit(tree.children[1])

        if type_var == "int" or type_var == "str":
            return f"{asm_expr}\nmov [{lhs}], rax\n"
        elif type_var == "double":
            return f"{asm_expr}\nmovsd [{lhs}], xmm0\n"

        raise TypeError(f"type de variable inconnu : {type_var}")

    def nop(self, tree):
        return "nop\n"

    def print(self, tree):

        type_expr = self.node_types[tree.children[0]]
        asm_expr = self.visit(tree.children[0])

        if type_expr == "int":
            return f"""{asm_expr}
                        mov rdi, format_entier
                        mov rsi, rax
                        xor rax, rax
                        call printf
                        """

        elif type_expr == "double":
            return f"""{asm_expr}
                        mov rdi, format_flottant
                        mov rax, 1
                        call printf
                    """
        elif type_expr == "str":
            return f"""{asm_expr}
                        mov rdi, format_chaine
                        mov rsi, rax
                        xor rax, rax
                        call printf
                    """

        raise TypeError(f"Impossible d'imprimer le type {type_expr}")

    def sequence(self, tree):
        return f"{self.visit(tree.children[0])}\n{self.visit(tree.children[1])}"

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

    def liste_vars(self, tree):
        res = []
        for i in range(len(tree.children)):
            type_var = tree.children[i].children[0].value
            nom_var = tree.children[i].children[1].value

            if type_var == "int":
                res.append(
                    f"""mov rdi, [argv]
                        add rdi, {(i+1)*8}
                        call atoi
                        mov [{nom_var}], rax"""
                )
            if type_var == "double":
                res.append(
                    f"""mov rdi, [argv]
                        add rdi, {(i+1)*8}
                        call atof
                        movsd [{nom_var}], xmm0"""
                )
            if type_var == "str":
                res.append(
                    f"""mov rdi, [argv]
                        add rdi, {(i+1)*8}
                        mov rax, [rdi]
                        mov [{nom_var}], rax"""
                )

        return "\n".join(res) + "\n"

    def _decls_vars(self, tree):
        return "\n".join(
            f"{tree.children[i].children[1].value}: dq 0"
            for i in range(len(tree.children))
        )

    def main(self, tree):

        parameters = self.visit(tree.children[0])
        commands = self.visit(tree.children[1])
        ret = self.visit(tree.children[2])

        declaration = self._decls_vars(tree.children[0])

        # Génération des constantes (const_float_0: dq 3.14)
        asm_consts = "\n".join(
            f"{label}: dq {valeur[1]}" for valeur, label in self.constantes.items()
        )

        squelette = open("squelette.asm").read()
        squelette = squelette.replace("DECL_VARS", declaration)
        squelette = squelette.replace("INIT_VARS", parameters)
        squelette = squelette.replace("CONSTANTES", asm_consts)
        squelette = squelette.replace("COMMAND", commands)
        squelette = squelette.replace("RETURN", ret)
        squelette = squelette.replace("  ", "")

        return squelette
