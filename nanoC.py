import lark

grammaire = lark.Lark(
    r"""
IDENTIFIER: /[a-zA-Z_][a-zA-Z_0-9]*/
OPBIN: /[+\-*\/<>]/
TYPE : "int" | "float" | "str" | "dict"
decl : TYPE IDENTIFIER | TYPE IDENTIFIER "<" TYPE "," TYPE ">"
vars : (decl ",")* decl -> liste_vars
expression : IDENTIFIER -> variable
           | SIGNED_INT -> entier
           | SIGNED_FLOAT -> double
           | "(" expression ")" -> expression
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
%import common.SIGNED_INT
%import common.SIGNED_FLOAT
%ignore WS
""",
    start="main",
)

compteur = iter(range(1_000_000))

constantes = {}

def construire_env(ast_vars) -> dict[str, str]:
    """
    Parcourt l'AST des variables et retourne un dictionnaire { 'nom_var': 'type_var' }
    Exemple: {'x': 'int', 'y': 'double'}
    """
    env = {}
    for decl in ast_vars.children:
        type_var = decl.children[0].value # "int" ou "double"
        nom_var = decl.children[1].value  # "x" ou "y"
        env[nom_var] = type_var
    return env


def pp_expression(ast):
    if ast.data in ("variable", "entier", "flottant"):
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


def asm_expression(ast, env:dict) -> tuple[str, str]:
    if ast.data == "entier":
        return "int", f"mov rax, {ast.children[0].value}\n"
        
    if ast.data == "double":
        valeur = ast.children[0].value
        if valeur not in constantes:
            label = f"const_float_{len(constantes)}"
            constantes[valeur] = label
        else:
            label = constantes[valeur]
        
        return "double", f"movsd xmm0, [{label}]\n"
        
    if ast.data == "variable":
        nom = ast.children[0].value
        type_var = env[nom]
        
        if type_var == "int":
            return "int", f"mov rax, [{nom}]\n"
        elif type_var == "double":
            return "double", f"movsd xmm0, [{nom}]\n"

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

    if ast.data == "binaire":
        type_g, asm_g = asm_expression(ast.children[0], env)
        op = ast.children[1].value
        type_d, asm_d = asm_expression(ast.children[2], env)

        if type_g != type_d:
            raise TypeError(f"Incompatibilité de types: impossible de faire '{type_g} {op} {type_d}'")

        if type_g == "int":
            base_asm = f"{asm_d}push rax\n{asm_g}pop rbx\n"
            opbin = {"+": "add", "-": "sub", "*": "imul"}
            
            if op in opbin:
                return "int", base_asm + f"{opbin[op]} rax, rbx\n"
            if op == "<":
                return "int", base_asm + "cmp rax, rbx\nsetl al\nmovzx rax, al\n"
            if op == ">":
                return "int", base_asm + "cmp rbx, rax\nsetg al\nmovzx rax, al\n"

            raise NotImplementedError(f"Opérateur non implémenté : {op}")
                
        if type_g == "double":
            # Attention, pour empiler xmm0, il faut utiliser la pile manuellement (rsp)
            base_asm = f"""{asm_d}
                           sub rsp, 8
                           movsd [rsp], xmm0
                           {asm_g}
                           movsd xmm1, [rsp]
                           add rsp, 8
                        """
            opbin = {"+": "addsd", "-": "subsd", "*": "mulsd", "/": "divsd"}
            
            if op in opbin:
                return "double", base_asm + f"{opbin[op]} xmm0, xmm1\n"
            if op == "<":
                return "int", base_asm + "ucomisd xmm0, xmm1\nsetb al\nmovzx rax, al\n"
            if op == ">":
                return "int", base_asm + "ucomisd xmm1, xmm0\nsetb al\nmovzx rax, al\n" 

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
    


def asm_commande(ast, env):
    if ast.data == "assignation":
        lhs = ast.children[0].value
        type_var = env[lhs]
        
        # On récupère le type et le code de l'expression
        type_expr, asm_expr = asm_expression(ast.children[1], env)
        
        if type_var != type_expr:
            raise TypeError(f"Assignation invalide: la variable {lhs} est de type {type_var}, mais on lui assigne un {type_expr}")

        if type_var == "int":
            return f"{asm_expr}\nmov [{lhs}], rax\n"
        elif type_var == "double":
            return f"{asm_expr}\nmovsd [{lhs}], xmm0\n"

    if ast.data == "pass":
        return "nop\n"

    if ast.data == "print":
        type_expr, asm_expr = asm_expression(ast.children[0], env)

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

    if ast.data == "sequence":
        cg = asm_commande(ast.children[0], env)
        cd = asm_commande(ast.children[1], env)
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
        test = asm_expression(ast.children[0], env)
        if test[0] != "int":
            raise TypeError("La condition n'est pas un booléen")

        cmd = asm_commande(ast.children[1], env)
        cpt = next(compteur)
        return f"""debut_{cpt}: {test[1]}
                    cmp rax, 0
                    jz fin_{cpt}
                    {cmd}
                    jmp debut_{cpt}
                    fin_{cpt}:"""

    if ast.data == "if":
        test = asm_expression(ast.children[0])
        if test[0] != "int":
            raise TypeError("La condition n'est pas un booléen")

        cmd = asm_commande(ast.children[1])
        cpt = next(compteur)
        return f"""{test[1]}
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

def asm_liste_vars(ast) -> str:
    res = []
    type_var = ast.children[i].children[0].value
    nom_var = ast.children[i].children[1].value

    for i in range(len(ast.children)):
        if ast.children[i].children[0].value == "dict":
            res.append(f"""mov rdi, [argv]
                            add rdi, {(i+1)*8}
                            call init_dict
                            mov [{ast.children[i].children[1].value}], rax""") 
            continue # TODO
            

        if type_var == "int":
            res.append(f"""mov rdi, [argv]
                            add rdi, {(i+1)*8}
                            call atoi
                            mov [{nom_var}], rax""")
        if type_var == "double":
            res.append(f"""mov rdi, [argv]
                            add rdi, {(i+1)*8}
                            call atof
                            movsd [{nom_var}], xmm0""")

    return "\n".join(res) + "\n"

def asm_decls_vars(ast):
    # TODO pour l'instant, on part du principe qu'on a des variables de taille 8
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
    ast_vars = ast.children[0]
    
    env = construire_env(ast_vars)
    
    decls = asm_decls_vars(ast_vars)
    vs = asm_liste_vars(ast_vars)
    cmd = asm_commande(ast.children[1], env)

    # Génération des constantes (const_float_0: dq 3.14)
    asm_consts = "\n".join(f"{label}: dq {valeur}" for valeur, label in constantes.items())
    if asm_consts:
        decls += "\n" + asm_consts + "\n"
    
    # On récupère juste le code asm de l'expression de retour (index 1 du tuple)
    type_ret, ret_asm = asm_expression(ast.children[2], env) 
    
    squelette = open("squelette.asm").read()
    squelette = squelette.replace("INIT_VARS", vs)
    squelette = squelette.replace("DECL_VARS", decls)
    squelette = squelette.replace("COMMAND", cmd)
    squelette = squelette.replace("RETURN", ret_asm)
    squelette = squelette.replace("  ", "")
    return squelette
    

if __name__ == "__main__":
    src = open("source.c").read()
    t = grammaire.parse(src)
    
    with open("resultat.asm", "w") as f:
        f.write(asm_main(t))
    with open("pretty.txt",  'w') as f:
        f.write(pp_main(t))