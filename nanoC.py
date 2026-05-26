from dataclasses import dataclass
import lark


@dataclass
class CodeResult:
    type: str
    asm: str


grammaire = lark.Lark(
    r"""
IDENTIFIER: /[a-zA-Z_][a-zA-Z_0-9]*/
OPBIN: /[+\-*\/<>]/
TYPE : "int" | "double" | "str"
decl : TYPE IDENTIFIER
vars : (decl ",")* decl -> liste_vars
expression : IDENTIFIER -> variable
           | SIGNED_INT -> entier
           | SIGNED_FLOAT -> double
           | "(" expression ")" -> expression
           | expression OPBIN expression -> binaire
           | TYPE "(" expression ")" -> conversion
commande : IDENTIFIER "=" expression ";" -> assignation
| commande* commande -> sequence
| "pass" -> pass
| "print" "(" expression ")" ";" -> print
| "if" "(" expression ")" "{" commande "}" -> if
| "while" "(" expression ")" "{" commande "}" -> while
main: "main" "(" vars ")" "{" commande "return" expression ";" "}"
%import common.WS
%import common.SIGNED_INT
%import common.SIGNED_FLOAT
%ignore WS
""",
    start="main",
)


class Compiler:
    def __init__(self):
        self.constantes: dict[str, str] = {}
        self.compteur = iter(range(1_000_000))

    def fresh_label(self) -> int:
        return next(self.compteur)

    def intern_float(self, valeur: str) -> str:
        """Retourne le label de la constante flottante, la crée si besoin."""
        if valeur not in self.constantes:
            self.constantes[valeur] = f"const_float_{len(self.constantes)}"
        return self.constantes[valeur]

    def construire_env(self, ast_vars) -> dict[str, str]:
        return {
            decl.children[1].value: decl.children[0].value for decl in ast_vars.children
        }

    def asm_decls_vars(self, ast_vars) -> str:
        return (
            "\n".join(f"{decl.children[1].value}: dq 0" for decl in ast_vars.children)
            + "\n"
        )

    def asm_liste_vars(self, ast_vars) -> str:
        lignes = []
        for i, decl in enumerate(ast_vars.children):
            type_var = decl.children[0].value
            nom_var = decl.children[1].value
            offset = (i + 1) * 8
            if type_var == "int":
                lignes.append(
                    f"mov rdi, [argv]\n"
                    f"add rdi, {offset}\n"
                    f"call atoi\n"
                    f"mov [{nom_var}], rax\n"
                )
            elif type_var == "double":
                lignes.append(
                    f"mov rdi, [argv]\n"
                    f"add rdi, {offset}\n"
                    f"call atof\n"
                    f"movsd [{nom_var}], xmm0\n"
                )
            else:
                raise TypeError(f"Type de paramètre non supporté : {type_var}")
        return "\n".join(lignes)

    def asm_expression(self, ast, env: dict) -> CodeResult:
        handler = {
            "entier": self._asm_entier,
            "double": self._asm_double,
            "variable": self._asm_variable,
            "conversion": self._asm_conversion,
            "binaire": self._asm_binaire,
            "expression": lambda a, e: self.asm_expression(a.children[0], e),
        }
        if ast.data not in handler:
            raise NotImplementedError(f"Nœud inconnu : {ast.data}")
        return handler[ast.data](ast, env)

    def _asm_entier(self, ast, env) -> CodeResult:
        return CodeResult("int", f"mov rax, {ast.children[0].value}\n")

    def _asm_double(self, ast, env) -> CodeResult:
        label = self.intern_float(ast.children[0].value)
        return CodeResult("double", f"movsd xmm0, [{label}]\n")

    def _asm_variable(self, ast, env) -> CodeResult:
        nom = ast.children[0].value
        if nom not in env:
            raise NameError(f"Variable inconnue : '{nom}'")
        type_var = env[nom]
        if type_var == "int":
            return CodeResult("int", f"mov rax, [{nom}]\n")
        if type_var == "double":
            return CodeResult("double", f"movsd xmm0, [{nom}]\n")
        raise TypeError(f"Type non supporté : {type_var}")

    def _asm_conversion(self, ast, env) -> CodeResult:
        type_cible = ast.children[0].value
        src = self.asm_expression(ast.children[1], env)
        if src.type == type_cible:
            return src
        if type_cible == "double" and src.type == "int":
            return CodeResult("double", src.asm + "cvtsi2sd xmm0, rax\n")
        if type_cible == "int" and src.type == "double":
            return CodeResult("int", src.asm + "cvttsd2si rax, xmm0\n")
        raise TypeError(f"Conversion impossible : {src.type} → {type_cible}")

    def _coerce_to_double(self, res: CodeResult) -> CodeResult:
        """Promotion int → double, no-op si déjà double."""
        if res.type == "double":
            return res
        return CodeResult("double", res.asm + "cvtsi2sd xmm0, rax\n")

    def _asm_binaire(self, ast, env) -> CodeResult:
        g = self.asm_expression(ast.children[0], env)
        op = ast.children[1].value
        d = self.asm_expression(ast.children[2], env)

        # Promotion implicite
        if g.type != d.type:
            g, d = self._coerce_to_double(g), self._coerce_to_double(d)

        if g.type == "int":
            return self._asm_binaire_int(g, op, d)
        if g.type == "double":
            return self._asm_binaire_double(g, op, d)
        raise TypeError(f"Type binaire non supporté : {g.type}")

    def _asm_binaire_int(self, g, op, d) -> CodeResult:
        base = f"{d.asm}push rax\n{g.asm}pop rbx\n"
        ops = {
            "+": "add rax, rbx",
            "-": "sub rax, rbx",
            "*": "imul rax, rbx",
            "<": "cmp rax, rbx\nsetl al\nmovzx rax, al",
            ">": "cmp rbx, rax\nsetg al\nmovzx rax, al",
        }
        if op not in ops:
            raise NotImplementedError(f"Opérateur entier non implémenté : {op}")
        return CodeResult("int", base + ops[op] + "\n")

    def _asm_binaire_double(self, g, op, d) -> CodeResult:
        base = (
            f"{d.asm}sub rsp, 8\nmovsd [rsp], xmm0\n"
            f"{g.asm}movsd xmm1, [rsp]\nadd rsp, 8\n"
        )
        ops = {
            "+": "addsd xmm0, xmm1",
            "-": "subsd xmm0, xmm1",
            "*": "mulsd xmm0, xmm1",
            "/": "divsd xmm0, xmm1",
            "<": "ucomisd xmm0, xmm1\nsetb al\nmovzx rax, al",
            ">": "ucomisd xmm1, xmm0\nsetb al\nmovzx rax, al",
        }
        if op not in ops:
            raise NotImplementedError(f"Opérateur flottant non implémenté : {op}")
        type_res = "int" if op in ("<", ">") else "double"
        return CodeResult(type_res, base + ops[op] + "\n")

    def asm_commande(self, ast, env: dict) -> str:
        handler = {
            "assignation": self._asm_assignation,
            "pass": self._asm_pass,
            "print": self._asm_print,
            "sequence": self._asm_sequence,
            "while": self._asm_while,
            "if": self._asm_if,
        }
        if ast.data not in handler:
            raise NotImplementedError(f"Commande inconnue : {ast.data}")
        return handler[ast.data](ast, env)

    def _asm_assignation(self, ast, env) -> str:
        lhs = ast.children[0].value
        if lhs not in env:
            raise NameError(f"Variable inconnue : '{lhs}'")
        type_var = env[lhs]
        src = self.asm_expression(ast.children[1], env)

        if type_var == "double" and src.type == "int":
            return src.asm + f"cvtsi2sd xmm0, rax\nmovsd [{lhs}], xmm0\n"
        if type_var == "int" and src.type == "double":
            raise TypeError(
                f"Assignation invalide : impossible d'assigner un double à '{lhs}' (int) sans conversion explicite"
            )
        if type_var != src.type:
            raise TypeError(
                f"Assignation invalide : '{lhs}' est {type_var}, expression est {src.type}"
            )

        if type_var == "int":
            return src.asm + f"mov [{lhs}], rax\n"
        if type_var == "double":
            return src.asm + f"movsd [{lhs}], xmm0\n"
        raise TypeError(f"Type non supporté : {type_var}")

    def _asm_pass(self, ast, env) -> str:
        return "nop\n"

    def _asm_print(self, ast, env) -> str:
        src = self.asm_expression(ast.children[0], env)
        if src.type == "int":
            return (
                f"{src.asm}"
                f"mov rdi, format_entier\n"
                f"mov rsi, rax\n"
                f"xor rax, rax\n"
                f"call printf\n"
            )
        if src.type == "double":
            return (
                f"{src.asm}"
                f"mov rdi, format_flottant\n"
                f"mov rax, 1\n"
                f"call printf\n"
            )
        raise TypeError(f"Type non imprimable : {src.type}")

    def _asm_sequence(self, ast, env) -> str:
        return "".join(self.asm_commande(child, env) for child in ast.children)

    def _asm_while(self, ast, env) -> str:
        test = self.asm_expression(ast.children[0], env)
        if test.type != "int":
            raise TypeError("La condition d'un while doit être un int")
        cmd = self.asm_commande(ast.children[1], env)
        cpt = self.fresh_label()
        return (
            f"debut_{cpt}:\n"
            f"{test.asm}"
            f"cmp rax, 0\n"
            f"jz fin_{cpt}\n"
            f"{cmd}"
            f"jmp debut_{cpt}\n"
            f"fin_{cpt}:\n"
        )

    def _asm_if(self, ast, env) -> str:
        test = self.asm_expression(ast.children[0], env)
        if test.type != "int":
            raise TypeError("La condition d'un if doit être un int")
        cmd = self.asm_commande(ast.children[1], env)
        cpt = self.fresh_label()
        return f"{test.asm}" f"cmp rax, 0\n" f"jz fin_{cpt}\n" f"{cmd}" f"fin_{cpt}:\n"


    def asm_main(self, ast) -> str:
        ast_vars = ast.children[0]
        env = self.construire_env(ast_vars)
        decls = self.asm_decls_vars(ast_vars)
        init = self.asm_liste_vars(ast_vars)

        cmd = self.asm_commande(ast.children[1], env)
        ret = self.asm_expression(ast.children[2], env)

        asm_consts = "\n".join(
            f"{label}: dq {valeur}" for valeur, label in self.constantes.items()
        )
        if asm_consts:
            decls += "\n" + asm_consts + "\n"

        squelette = open("squelette.asm").read()
        return (
            squelette.replace("INIT_VARS", init)
            .replace("DECL_VARS", decls)
            .replace("COMMAND", cmd)
            .replace("RETURN", ret.asm)
            .replace("  ", "")
        )


if __name__ == "__main__":
    src = open("source.c").read()
    ast = grammaire.parse(src)
    with open("resultat.asm", "w") as f:
        compiler = Compiler()
        f.write(compiler.asm_main(ast))
