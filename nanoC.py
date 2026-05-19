import lark

grammaire = lark.Lark(
    r"""
IDENTIFIER: /[a-zA-Z_][a-zA-Z_0-9]*/
OPBIN: /[+\-*\/<>]/
TYPE : "int" | "float" | "str" | "dict"
decl : TYPE IDENTIFIER | TYPE IDENTIFIER "<" TYPE "," TYPE ">"
vars : (decl ",")* decl -> liste_vars
expression : IDENTIFIER -> variable
           | SIGNED_NUMBER -> entier
           | expression OPBIN expression -> binaire
           | IDENTIFIER "[" expression "]" -> dict_access
commande : IDENTIFIER "=" expression ";" -> assignation 
| commande* commande -> sequence
| "pass" -> pass
| "print" "(" expression ")" ";" -> print
| "if" "(" expression ")" "{" commande "}" -> if
| "while" "(" expression ")" "{" commande "}" -> while

| IDENTIFIER "[" expression "]" "=" expression ";" -> assignation_dict
| IDENTIFIER "=" "{" (expression ":" expression ",")* expression ":" expression "}" ";" -> assignation_dict_literal
| "del" IDENTIFIER "[" expression "]" ";" -> del_dict
| "foreach" "(" IDENTIFIER "in" IDENTIFIER ")" "{" commande "}" -> foreach_dict

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
    if ast.data == "binaire":
        eg = f"{pp_expression(ast.children[0])}"
        op = ast.children[1].value
        ed = f"{pp_expression(ast.children[2])}"
        return f"{eg} {op} {ed}"
    if ast.data == "dict_access":
        dict_name = ast.children[0].value
        key = pp_expression(ast.children[1])
        return f"{dict_name}[{key}]"


def asm_expression(ast):
    if ast.data == "variable":
        return f"mov rax, [{ast.children[0].value}]\n"
    if ast.data == "entier":
        return f"mov rax, {ast.children[0].value}\n"

    if ast.data == "dict_access":
        dict_name = ast.children[0].value
        key_asm = asm_expression(ast.children[1])
        return f"""{key_asm}
                    mov rsi, rax
                    mov rdi, [{dict_name}]
                    call get_from_dict
                    """
    
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
        return f"{cg}\n{cd}"
    if ast.data in ("if", "while"):
        cg = pp_expression(ast.children[0])
        cd = pp_commande(ast.children[1])
        return f"{ast.data}({cg}) {{{cd}}}"

    if ast.data == "assignation_dict":
        dict_name = ast.children[0].value
        key = pp_expression(ast.children[1])
        value = pp_expression(ast.children[2])
        return f"{dict_name}[{key}] = {value};"
    if ast.data == "assignation_dict_literal":
        dict_name = ast.children[0].value
        pairs = []
        for i in range(1, len(ast.children), 2):
            key = pp_expression(ast.children[i])
            value = pp_expression(ast.children[i + 1])
            pairs.append(f"{key}: {value}")
        return f"{dict_name} = {{{', '.join(pairs)}}};"
    if ast.data == "del_dict":
        dict_name = ast.children[0].value
        key = pp_expression(ast.children[1])
        return f"del {dict_name}[{key}];"
    if ast.data == "foreach_dict":
        var_name = ast.children[0].value
        dict_name = ast.children[1].value
        cmd = pp_commande(ast.children[2])
        return f"foreach({var_name} in {dict_name}) \n{{\n{cmd}\n}}"
    


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
    
    if ast.data == "assignation_dict":
        dict_name = ast.children[0].value
        key = asm_expression(ast.children[1])
        value = asm_expression(ast.children[2])
        return f"""{value}
                    push rax
                    {key}
                    pop rbx
                    mov rdx, rbx
                    mov rsi, rax
                    mov rdi, [{dict_name}]
                    call set_in_dict
                    """


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
    res = []
    for i in range(len(ast.children)):
        res.append(ast.children[i].children[1]) 
    return ", ".join(res)

def asm_liste_vars(ast):
    # TODO modifier selon le type
    res = []
    for i in range(len(ast.children)):
        if ast.children[i].children[0].value == "dict":
            res.append(f"""mov rdi, [argv]
                            add rdi, {(i+1)*8}
                            call init_dict
                            mov [{ast.children[i].children[1].value}], rax""") 
        else:
            res.append(f"""mov rdi, [argv]
                            add rdi, {(i+1)*8}
                            call atoi
                            mov [{ast.children[i].children[1].value}], rax""")
    return "\n".join(res) + "\n"

def asm_decls_vars(ast):
    # TODO pour l'instant, on part du principe qu'on a des int
    # ast.children[i].children[0] contient le type
    result = []
    for i in range(len(ast.children)):

        if ast.children[i].children[0].value == "dict":
            result.append(f"{ast.children[i].children[1].value} db 0 ; dict {ast.children[i].children[2].value} -> {ast.children[i].children[3].value}")
        else:
            result.append(f"{ast.children[i].children[1].value} dq 0 ; {ast.children[i].children[0].value}")
    return "\n".join(result) + "\n"

def pp_decl_vars(ast):
    result = []
    for i in range(len(ast.children)):
        if ast.children[i].children[0].value == "dict":
            if len(ast.children[i].children) == 4:
                result.append(f"dict {ast.children[i].children[1].value}<{ast.children[i].children[2].value},{ast.children[i].children[3].value}>;")
            else:
                result.append(f"dict {ast.children[i].children[1].value};")
        else:
            result.append(f"{ast.children[i].children[0].value} {ast.children[i].children[1].value};")
    return "\n".join(result) + "\n"

def pp_main(ast):
    decls = pp_decl_vars(ast.children[0])
    vs = pp_liste_vars(ast.children[0])
    cmd = pp_commande(ast.children[1])
    ret = pp_expression(ast.children[2])
    return f"""main({vs}) {{
{decls}
{cmd}
return {ret};
}}
"""

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
    with open("pretty.txt",  'w') as f:
        f.write(pp_main(t))