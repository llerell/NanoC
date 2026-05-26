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
    env = {}
    for decl in ast_vars.children:
        type_var = decl.children[0].value
        nom_var = decl.children[1].value
        if decl.children[0].value == "dict":
            type_cle = decl.children[2].value
            type_valeur = decl.children[3].value
            type_var = f"dict<{type_cle},{type_valeur}>"
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
        elif type_var.startswith("dict"):
            return type_var, f"mov rax, [{nom}]\n"
        else:
            raise TypeError(f"Type de variable non supporté : {type_var}")

    if ast.data == "dict_access":
        dict_name = ast.children[0].value
        key_type, key_asm = asm_expression(ast.children[1], env)
        dict_type = env[dict_name]
        if not dict_type.startswith("dict"):
            raise TypeError(f"Le type de {dict_name} n'est pas un dictionnaire")
        
        val_type = dict_type.split("<")[1].split(",")[1].replace(">", "")
        return val_type, f"""{key_asm}
                    mov rsi, rax
                    mov rdi, [{dict_name}]
                    call get_from_dict
                    """

    if ast.data == "binaire":
        type_g, asm_g = asm_expression(ast.children[0], env)
        type_d, asm_d = asm_expression(ast.children[2], env)
        op = ast.children[1].value

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

    raise NotImplementedError(f"Expression non implémentée : {ast.data}")


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
        key_type, key_asm = asm_expression(ast.children[1], env)
        val_type, val_asm = asm_expression(ast.children[2], env)
        
        if env[dict_name] != f"dict<{key_type},{val_type}>":
            raise TypeError(f"Assignation invalide: la variable {dict_name} est de type {env[dict_name]}, mais on lui assigne une paire ({key_type}, {val_type})")
        
        if val_type in ("int", "double"):
            save_val = "sub rsp, 8\nmovsd [rsp], xmm0\n" if val_type == "double" else "push rax\n"
            restore_val = "mov rdx, [rsp]\nadd rsp, 8\n" if val_type == "double" else "pop rdx\n"
        else:
            save_val = "push rax\n"
            restore_val = "pop rdx\n"

        if key_type in ("int", "double"):
            save_key = "sub rsp, 8\nmovsd [rsp], xmm0\n" if key_type == "double" else "push rax\n"
            restore_key = "mov rsi, [rsp]\nadd rsp, 8\n" if key_type == "double" else "pop rsi\n"
        else:
            save_key = "push rax\n"
            restore_key = "pop rsi\n"

        return f"""{val_asm}
                    {save_val}
                    {key_asm}
                    {save_key}
                    lea rdi, [{dict_name}]
                    {restore_key}
                    {restore_val}
                    call set_in_dict
                    """

    if ast.data == "assignation_dict_literal":
        dict_name = ast.children[0].value
        dict_type = env[dict_name]
        asm_code = "call init_dict\nmov [" + dict_name + "], rax\n"
        
        for i in range(1, len(ast.children), 2):
            key_node = ast.children[i]
            val_node = ast.children[i+1]
            
            key_type, key_asm = asm_expression(key_node, env)
            val_type, val_asm = asm_expression(val_node, env)
            
            if f"dict<{key_type},{val_type}>" != dict_type:
                raise TypeError(f"La paire {key_type}:{val_type} ne correspond pas au type attendu de {dict_name} ({dict_type})")
            
            save_val = "sub rsp, 8\nmovsd [rsp], xmm0\n" if val_type in ("double", "str") else "push rax\n"
            restore_val = "mov rdx, [rsp]\nadd rsp, 8\n" if val_type in ("double", "str") else "pop rdx\n"
                
            save_key = "sub rsp, 8\nmovsd [rsp], xmm0\n" if key_type in ("double", "str") else "push rax\n"
            restore_key = "mov rsi, [rsp]\nadd rsp, 8\n" if key_type in ("double", "str") else "pop rsi\n"
                
            asm_code += f"""
            {val_asm}
            {save_val}
            {key_asm}
            {save_key}
            lea rdi, [{dict_name}]
            {restore_key}
            {restore_val}
            call set_in_dict
            """
        return asm_code
    
    if ast.data == "del_dict":
        dict_name = ast.children[0].value
        key_type, key_asm = asm_expression(ast.children[1], env)
        
        if key_type == "double":
            save_key = "sub rsp, 8\nmovsd [rsp], xmm0\n"
            restore_key = "mov rsi, [rsp]\nadd rsp, 8\n"
        else:
            save_key = "push rax\n"
            restore_key = "pop rsi\n"
            
        return f"""
        {key_asm}
        {save_key}
        mov rdi, [{dict_name}]
        {restore_key}
        call delete_from_dict
        """

    if ast.data == "foreach_dict":
        var_name = ast.children[0].value
        dict_name = ast.children[1].value
        body_cmd = ast.children[2]
        
        dict_type = env[dict_name]
        expected_key_type = dict_type.split("<")[1].split(",")[0]
        if env[var_name] != expected_key_type:
            raise TypeError(f"La variable de boucle '{var_name}' ({env[var_name]}) doit être du même type que les clés du dictionnaire ({expected_key_type})")
            
        cpt = next(compteur)
        asm_body = asm_commande(body_cmd, env)
        
        return f"""
        ; Récupération de la taille totale du dictionnaire
        mov rdi, [{dict_name}]
        call dict_get_size
        push rax                 ; [rsp+8] = taille totale du dict
        
        mov rax, 0
        push rax                 ; [rsp] = index de boucle actuel (i = 0)
        
        debut_foreach_{cpt}:
        ; Condition de boucle : i < taille
        mov rax, [rsp]
        mov rbx, [rsp+8]
        cmp rax, rbx
        jge fin_foreach_{cpt}
        
        ; Récupération de la clé stockée à l'index `i`
        mov rdi, [{dict_name}]
        mov rsi, [rsp]
        call dict_get_key_by_index
        
        ; Affectation de la clé à la variable de boucle
        mov [{var_name}], rax
        
        ; Corps de la boucle foreach
        {asm_body}
        
        ; Incrémentation de l'index i
        mov rax, [rsp]
        inc rax
        mov [rsp], rax
        jmp debut_foreach_{cpt}
        
        fin_foreach_{cpt}:
        add rsp, 16              ; Nettoyage des variables de boucle de la pile
        """

    if ast.data == "while":
        test_type, test_asm = asm_expression(ast.children[0], env)
        if test_type != "int":
            raise TypeError("La condition n'est pas un booléen")

        cmd = asm_commande(ast.children[1], env)
        cpt = next(compteur)
        return f"""debut_{cpt}: {test_asm}
                    cmp rax, 0
                    jz fin_{cpt}
                    {cmd}
                    jmp debut_{cpt}
                    fin_{cpt}:"""

    if ast.data == "if":
        test_type, test_asm = asm_expression(ast.children[0], env)
        if test_type != "int":
            raise TypeError("La condition n'est pas un booléen")

        cmd = asm_commande(ast.children[1], env)
        cpt = next(compteur)
        return f"""{test_asm}
                    cmp rax, 0
                    jz fin_{cpt}
                    {cmd}
                    fin_{cpt}:
                    """


def pp_liste_vars(ast):
    res = []
    for i in range(len(ast.children)):
        res.append(ast.children[i].children[1].value) 
    return ", ".join(res)

def asm_liste_vars(ast) -> str:
    res = []
    for i in range(len(ast.children)):
        type_var = ast.children[i].children[0].value
        nom_var = ast.children[i].children[1].value
        if type_var == "dict":
            res.append(f"""mov rdi, [argv]
                            add rdi, {(i+1)*8}
                            call init_dict
                            mov [{nom_var}], rax""") 
            continue
            
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
    result = []
    for i in range(len(ast.children)):
        nom_var = ast.children[i].children[1].value
        if ast.children[i].children[0].value == "dict":
            result.append(f"{nom_var} dq 0 ; dict {ast.children[i].children[2].value} -> {ast.children[i].children[3].value}")
        else:
            result.append(f"{nom_var} dq 0 ; {ast.children[i].children[0].value}")
    return "\n".join(result) + "\n"

def pp_decl_vars(ast):
    result = []
    for i in range(len(ast.children)):
        nom_var = ast.children[i].children[1].value
        if ast.children[i].children[0].value == "dict":
            if len(ast.children[i].children) == 4:
                result.append(f"dict {nom_var}<{ast.children[i].children[2].value},{ast.children[i].children[3].value}>;")
            else:
                result.append(f"dict {nom_var};")
        else:
            result.append(f"{ast.children[i].children[0].value} {nom_var};")
    return "\n".join(result) + "\n"

def pp_main(ast):
    decls = pp_decl_vars(ast.children[0])
    vs = pp_liste_vars(ast.children[0])
    cmd = pp_commande(ast.children[1])
    ret = pp_expression(ast.children[2])
    return f"""main({vs}) {{\n{decls}\n{cmd}\nreturn {ret};\n}}\n"""

def asm_main(ast):
    ast_vars = ast.children[0]
    env = construire_env(ast_vars)
    
    decls = asm_decls_vars(ast_vars)
    vs = asm_liste_vars(ast_vars)
    cmd = asm_commande(ast.children[1], env)

    asm_consts = "\n".join(f"{label}: dq {valeur}" for valeur, label in constantes.items())
    if asm_consts:
        decls += "\n" + asm_consts + "\n"
    
    type_ret, ret_asm = asm_expression(ast.children[2], env) 
    
    squelette = open("squelette.asm").read()
    dict_squelette = open("dict_squelette.asm").read()
    squelette = squelette.replace("DICT", dict_squelette) 
    squelette = squelette.replace("INIT_VARS", vs)
    squelette = squelette.replace("DECL_VARS", decls)
    squelette = squelette.replace("COMMAND", cmd)
    squelette = squelette.replace("RETURN", ret_asm)
    squelette = squelette.replace("  ", "")
    return squelette
    

if __name__ == "__main__":
    src = open("source.c").read()
    t = grammaire.parse(src)
    with open("pretty.txt",  'w') as f:
        f.write(pp_main(t))   
    with open("resultat.asm", "w") as f:
        f.write(asm_main(t))