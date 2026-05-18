import lark

grammaire = lark.Lark(
    r"""
IDENTIFIER: /[a-zA-Z_][a-zA-Z_0-9]*/
OPBIN: /[+\-*\/<>]/
vars : (IDENTIFIER ",")* IDENTIFIER -> liste_vars
expression : IDENTIFIER -> variable
           | SIGNED_NUMBER -> entier
           | expression OPBIN expression -> binaire
commande : IDENTIFIER "=" expression ";" -> assignation
| commande* commande -> sequence
| "pass" -> pass
| "print" "(" expression ")" ";" -> print
| "if" "(" expression ")" "{" commande "}" -> if
| "while" "(" expression ")" "{" commande "}" -> while
main: "main" "(" vars ")" "{" commande "return" expression ";" "}"
%import common.WS
%import common.SIGNED_NUMBER
%ignore WS
""",
    start="main",
)

compteur = iter(range(1_000_000))

def pp_expression(ast):
    if ast.data in ("variable", "entier"):
        return ast.children[0].value
    eg = f"{pp_expression(ast.children[0])}"
    op = ast.children[1].value
    ed = f"{pp_expression(ast.children[2])}"
    return f"{eg} {op} {ed}"


def asm_expression(ast):
    if ast.data == "variable":
        return f"mov rax, [{ast.children[0].value}]\n"
    if ast.data == "entier":
        return f"mov rax, {ast.children[0].value}\n"

    eg = f"{asm_expression(ast.children[0])}"
    op = ast.children[1].value
    ed = f"{asm_expression(ast.children[2])}"

    base_asm = f"""{ed}push rax
                        {eg}pop rbx
                        """

    opbin = {"+": "add", "-": "sub", "*": "imul"}

    if op in opbin:
        return base_asm + f"{opbin[op]} rax, rbx\n"

    if op == "<":
        return base_asm + "cmp rax, rbx\nsetl al\nmovzx rax, al\n"
    if op == ">":
        return base_asm + "cmp rax, rbx\nsetg al\nmovzx rax, al\n"

    raise NotImplementedError(f"Opérateur inconnu : {op}")


def pp_commande(ast):
    if ast.data == "assignation":
        lhs = ast.children[0].value
        rhs = pp_expression(ast.children[1])
        return f"{lhs} = {rhs};"
    if ast.data == "pass":
        return "pass"
    if ast.data == "print":
        return f"print({pp_expression(ast.children[0])});"
    if ast.data == "sequence":
        cg = pp_commande(ast.children[0])
        cd = pp_commande(ast.children[1])
        return f"{cg}{cd}"
    if ast.data in ("if", "while"):
        cg = pp_expression(ast.children[0])
        cd = pp_commande(ast.children[1])
        return f"{ast.data}({cg}) {{{cd}}}"


def asm_commande(ast):
    if ast.data == "assignation":
        lhs = ast.children[0].value
        rhs = asm_expression(ast.children[1])
        return f"{rhs}\nmov [{lhs}], rax\n"

    if ast.data == "pass":
        return "nop\n"

    if ast.data == "print":
        return f"""{asm_expression(ast.children[0])}
                    mov rdi, format
                    mov rsi, rax
                    xor rax, rax
                    call printf"""

    if ast.data == "sequence":
        cg = asm_commande(ast.children[0])
        cd = asm_commande(ast.children[1])
        return f"{cg}{cd}"

    if ast.data == "while":
        test = asm_expression(ast.children[0])
        cmd = asm_commande(ast.children[1])
        cpt = next(compteur)
        return f"""debut_{cpt}: {test}
                    cmp rax, 0
                    jz fin_{cpt}
                    {cmd}
                    jmp debut_{cpt}
                    fin_{cpt}:"""

    if ast.data == "if":
        test = asm_expression(ast.children[0])
        cmd = asm_commande(ast.children[1])
        cpt = next(compteur)
        return f"""{test}
        cmp rax, 0
        jz fin_{cpt}
        {cmd}
        fin_{cpt}:
        """


def pp_liste_vars(ast):
    return ", ".join((v.value for v in ast.children))


def asm_liste_vars(ast):
    res = []
    for i in range(len(ast.children)):
        res.append(f"""mov rdi, [argv]
                        add rdi, {(i+1)*8}
                        call atoi
                        mov [{ast.children[i].value}], rax""")
    return "\n".join(res) + "\n"

def asm_decls_vars(ast):
    return "\n".join(f"{ast.children[i].value}: dq 0" for i in range(len(ast.children))) + "\n"

def pp_main(ast):
    vs = pp_liste_vars(ast.children[0])
    cmd = pp_commande(ast.children[1])
    ret = pp_expression(ast.children[2])
    return f"main({vs})\n    {cmd}\n    return ({ret});"

def asm_main(ast):
    decls = asm_decls_vars(ast.children[0])
    vs = asm_liste_vars(ast.children[0])
    cmd = asm_commande(ast.children[1])
    ret = asm_expression(ast.children[2])
    squelette = open("squelette.asm").read()
    squelette = squelette.replace("INIT_VARS", vs)
    squelette = squelette.replace("DECL_VARS", decls)
    squelette = squelette.replace("COMMAND", cmd)
    squelette = squelette.replace("RETURN", ret)
    squelette = squelette.replace("  ", "")


    return squelette
    

if __name__ == "__main__":
    src = open("source.c").read()
    t = grammaire.parse(src)
    with open("resultat.asm", "w") as f:
        f.write(asm_main(t))