import lark

# TODO: types de dict: convertir
grammaire = lark.Lark(
    r"""
IDENTIFIER: /[a-zA-Z_][a-zA-Z_0-9]*/
STRING : /"[^"]*"/
CHAR : /'[^']'/
decl : TYPE IDENTIFIER
OPBIN: /<=|>=|==|!=|[+\-*\/<>%&|^]/
PRIMITIVE_TYPE : "int" | "double" | "str"
COMPOSITE_TYPE : "dict"
full_type : PRIMITIVE_TYPE | COMPOSITE_TYPE "<" PRIMITIVE_TYPE ","  full_type ">"
decl : PRIMITIVE_TYPE IDENTIFIER | COMPOSITE_TYPE IDENTIFIER "<" PRIMITIVE_TYPE ","  full_type ">"

vars : (decl ",")* decl -> liste_vars
expression : IDENTIFIER -> variable
           | SIGNED_INT -> entier
           | SIGNED_FLOAT -> double
           | "(" expression ")" -> expression
           | expression OPBIN expression -> binaire
           | STRING -> chaine
           | CHAR -> caractere
           | "len" "(" expression ")" -> len
           | "charAt" "(" expression "," expression ")" -> charat
           | "atoi" "(" expression ")" -> atoi
           | "!" expression -> non_logique
           | TYPE "(" expression ")" -> conversion
           | IDENTIFIER "[" expression "]" -> dict_access
           | "!" expression -> non_logique
           | PRIMITIVE_TYPE "(" expression ")" -> conversion
           | "{" (expression ":" expression ",")* expression ":" expression "}" -> dict_literal
commande : IDENTIFIER "=" expression ";" -> assignation
| commande* commande -> sequence
| "pass" -> pass
| "print" "(" expression ")" ";" -> print
| "if" "(" expression ")" "{" commande "}" -> if
| "while" "(" expression ")" "{" commande "}" -> while
| IDENTIFIER "[" expression "]" "=" expression ";" -> assignation_dict
| "del" IDENTIFIER "[" expression "]" ";" -> del_dict
| "foreach" "(" IDENTIFIER "in" IDENTIFIER ")" "{" commande "}" -> foreach_dict

main: "main" "(" vars ")" "{" commande "return" expression ";" "}"
%import common.WS
%import common.SIGNED_INT
%import common.SIGNED_FLOAT
%ignore WS
%ignore /\/\/[^\n\r]*/
%ignore /\/\*[\s\S]*?\*\//
""",
    start="main",
)

compteur = iter(range(1_000_000))

constantes = {}
temp_dict_labels = []


def construire_env(ast_vars) -> dict[str, str]:
    """
    Parcourt l'AST des variables et retourne un dictionnaire { 'nom_var': 'type_var' }
    Exemple: {'x': 'int', 'y': 'double'}
    """
    env = {}
    for decl in ast_vars.children:
        type_var = decl.children[0].value
        nom_var = decl.children[1].value
        if decl.children[0].value == "dict":
            type_cle = decl.children[2].value
            type_valeur = pp_types(decl.children[3])
            type_var = f"dict<{type_cle},{type_valeur}>"
        env[nom_var] = type_var
    return env


def pp_expression(ast):
    if ast.data in ("variable", "entier", "flottant", "chaine", "caractere"):
        return ast.children[0].value
    if ast.data=="len":
        return f"len({pp_expression(ast.children[0])})"
    if ast.data=="atoi":
        return f"atoi({pp_expression(ast.children[0])})"
    if ast.data=="charAt":
        return f"charat({pp_expression(ast.children[0])}, {pp_expression(ast.children[1])})"
    if ast.data == "binaire":
        eg = f"{pp_expression(ast.children[0])}"
        op = ast.children[1].value
        ed = f"{pp_expression(ast.children[2])}"
        return f"{eg} {op} {ed}"
    if ast.data == "dict_access":
        dict_name = ast.children[0].value
        key = pp_expression(ast.children[1])
        return f"{dict_name}[{key}]"
    if ast.data == "dict_literal":
        pairs = []
        for i in range(0, len(ast.children)-1, 2):
            key = pp_expression(ast.children[i])
            value = pp_expression(ast.children[i + 1])
            pairs.append(f"{key}: {value}")
        return f"{{{', '.join(pairs)}}};"      

def asm_expression(ast, env: dict) -> tuple[str, str]:
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
    if ast.data == "conversion":
        type_cible = ast.children[0].value
        type_src, asm_src = asm_expression(ast.children[1], env)

        if type_src == type_cible:
            return type_cible, asm_src

        if type_cible == "double" and type_src == "int":
            return "double", asm_src + "cvtsi2sd xmm0, rax\n"

        if type_cible == "int" and type_src == "double":
            # arrondi au plus proche
            return "int", asm_src + "cvtsd2si rax, xmm0\n"

        raise TypeError(f"Conversion impossible : {type_src} vers {type_cible}")

    if ast.data == "non_logique":
        type_expr, asm_expr = asm_expression(ast.children[0], env)
        if type_expr != "int":
            raise TypeError("Le non logique ne s'applique qu'aux variables de type int")
        asm = f"""{asm_expr}
                  cmp rax, 0
                  sete al
                  movzx rax, al
                  """
        return "int", asm

    if ast.data == "binaire":
        type_g, asm_g = asm_expression(ast.children[0], env)
        op = ast.children[1].value
        type_d, asm_d = asm_expression(ast.children[2], env)

        if type_g == "int" and type_d == "double":
            asm_g = asm_g + "cvtsi2sd xmm0, rax\n"
            type_g = "double"
        elif type_g == "double" and type_d == "int":
            asm_d = asm_d + "cvtsi2sd xmm0, rax\n"
            type_d = "double"

        if type_g == type_d == "int":
            base_asm = f"{asm_d}push rax\n{asm_g}pop rbx\n"
            opbin = {"+": "add", "-": "sub", "*": "imul"}
            if op in opbin:
                return "int", base_asm + f"{opbin[op]} rax, rbx\n"
            if op == "<":
                return "int", base_asm + "cmp rax, rbx\nsetl al\nmovzx rax, al\n"
            if op == ">":
                return "int", base_asm + "cmp rbx, rax\nsetg al\nmovzx rax, al\n"
            raise NotImplementedError(f"Opérateur non implémenté : {op}")
                
        if type_g == type_d == "double":
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


            if op == "/":
                return "int", base_asm + "cqo\nidiv rbx\n"
            if op == "%":
                return "int", base_asm + "cqo\nidiv rbx\nmov rax, rdx\n"

            if op in opbin:
                return "int", base_asm + f"{opbin[op]} rax, rbx\n"
            if op in opcomp:
                return (
                    "int",
                    base_asm + f"cmp rax, rbx\n{opcomp[op]} al\nmovzx rax, al\n",
                )

            raise NotImplementedError(f"Opérateur non implémenté : {op}")

        if type_g == type_d == "double":
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
                return "double", base_asm + f"{opbin[op]} xmm0, xmm1\n"
            if op in opcomp:
                return (
                    "int",
                    base_asm + f"ucomisd xmm0, xmm1\n{opcomp[op]} al\nmovzx rax, al\n",
                )

        raise TypeError(
            f"Incompatibilité de types: impossible de faire '{type_g} {op} {type_d}'"
        )

    if ast.data == "dict_literal":
        dict_name = f"dict_{next(compteur)}"
        temp_dict_labels.append(dict_name)
        asm_code = "call init_dict\nmov [" + dict_name + "], rax\n"
        
        key_type = asm_expression(ast.children[0], env)[0]
        val_type = asm_expression(ast.children[1], env)[0]
        dict_type = f"dict<{key_type},{val_type}>"

        for i in range(0, len(ast.children)-1, 2):
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
        asm_code += f"mov rax, [{dict_name}]\n"
        return f"dict<{key_type},{val_type}>", asm_code
    
    raise NotImplementedError(f"Nœud inconnu : {ast.data}")

            # vérification de la présence de la constante
            if (type_lit, valeur) not in constantes:
                label = f"const_{type_lit}_{len(constantes)}"
                constantes[(type_lit, valeur)] = label
            else:
                label = constantes[(type_lit, valeur)]

            return "double", f"movsd xmm0, [{label}]\n"

        case "variable":
            nom = ast.children[0].value
            type_var = env[nom]

            if type_var == "int":
                return "int", f"mov rax, [{nom}]\n"
            elif type_var == "double":
                return "double", f"movsd xmm0, [{nom}]\n"
            elif type_var=="str":
                return "str", f"mov rax, [{nom}]\n"
            
            raise TypeError(f"type de variable inconnu : {type_var}")


        case "chaine":
            lbl = f"lit_{next(compteur)}"
            valeur = ast.children[0].value
            constantes[lbl] = valeur
            return "str", f"mov rax, {lbl}\n"
        #il y aura écrit lit_1 : "abc" dans .data, NASM regardera où en est son compteur interne, l'adresse correspondante est associée à lit_1
        #plus tard quand il voit mov rax, lit_1 il remplace lit_1 par l'adresse associée où a été stockée "abc"
            
        case "caractere":
            return "int", f"mov rax, {ast.children[0].value}\n"
        #un carac est vu comme sa valeur ascii par le processeur

        case "conversion":
            type_cible = ast.children[0].value
            type_src, asm_src = asm_expression(ast.children[1], env)

            if type_src == type_cible:
                return type_cible, asm_src

            if type_cible == "double" and type_src == "int":
                return "double", asm_src + "cvtsi2sd xmm0, rax\n"

            if type_cible == "int" and type_src == "double":
                # arrondi au plus proche
                return "int", asm_src + "cvtsd2si rax, xmm0\n"

            raise TypeError(f"Conversion impossible : {type_src} vers {type_cible}")

        case "non_logique":
            type_expr, asm_expr = asm_expression(ast.children[0], env)
            if type_expr != "int":
                raise TypeError("Le non logique ne s'applique qu'aux variables de type int")
            asm = f"""{asm_expr}
                    cmp rax, 0
                    sete al
                    movzx rax, al
                    """
            return "int", asm

        case "binaire":
            type_g, asm_g = asm_expression(ast.children[0], env)
            op = ast.children[1].value
            type_d, asm_d = asm_expression(ast.children[2], env)
            
            if (type_g == "str" and type_d =="str" and op=="+"):
                return "str", asm_concat(asm_g,asm_d)

            if type_g == "int" and type_d == "double":
                asm_g = asm_g + "cvtsi2sd xmm0, rax\n"
                type_g = "double"
            elif type_g == "double" and type_d == "int":
                asm_d = asm_d + "cvtsi2sd xmm0, rax\n"
                type_d = "double"

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
                    return "int", base_asm + "cqo\nidiv rbx\n"
                if op == "%":
                    return "int", base_asm + "cqo\nidiv rbx\nmov rax, rdx\n"

                if op in opbin:
                    return "int", base_asm + f"{opbin[op]} rax, rbx\n"
                if op in opcomp:
                    return (
                        "int",
                        base_asm + f"cmp rax, rbx\n{opcomp[op]} al\nmovzx rax, al\n",
                    )

                raise NotImplementedError(f"Opérateur non implémenté : {op}")

            if type_g == type_d == "double":
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
                    return "double", base_asm + f"{opbin[op]} xmm0, xmm1\n"
                if op in opcomp:
                    return (
                        "int",
                        base_asm + f"ucomisd xmm0, xmm1\n{opcomp[op]} al\nmovzx rax, al\n",
                    )

            raise TypeError(
                f"Incompatibilité de types: impossible de faire '{type_g} {op} {type_d}'"
            )

        case "atoi":
            # On évalue ce qu'il y a dans les parenthèses
            type_expr, code = asm_expression(ast.children[0],env) #si atoi("123"), dans code il y a l'asm qui met l'adresse de "123" dans rax
            # On génère le code : on met l'adresse de la chaîne dans rdi, puis on appelle atoi
            return "int", f"""{code}
                            mov rdi, rax
                            call atoi
                            """
        case "len" :
            type_expr, code = asm_expression(ast.children[0],env) #même chose
            return "int", f"""{code}
                    mov rdi, rax
                    call strlen
                    """    
        case "charat":
            str_asm = asm_expression(ast.children[0],env)[1]
            idx_asm = asm_expression(ast.children[1],env)[1]
            # On évalue d'abord l'index qu'on pousse sur la pile, puis l'adresse de la chaîne
            code_charat = idx_asm + "push rax\n" + str_asm + "pop rbx\nmovzx rax, byte [rax + rbx]\n"
            return "int", code_charat
        #byte : ne lire qu'un seul octet (un carac fait 8bits)
        # au final, rax contient la valeur numérique du caractère demandé
        case _:
            raise NotImplementedError(f"Nœud inconnu : {ast.data}")

def asm_concat(asm_g,asm_d):    #TODOTODOTODOTODO
    """ Génère le code de concaténation de deux chaînes via malloc """
    return f"""
    {asm_d}
    push rax            
    {asm_g}
    push rax            
    mov rdi, rax
    call strlen         
    push rax            
    mov rdi, [rsp + 16] 
    call strlen         
    pop rbx             
    add rax, rbx        
    inc rax             
    mov rdi, rax        
    call malloc         
    push rax            
    mov rdi, rax        
    mov rsi, [rsp + 8]  
    call strcpy         
    mov rdi, [rsp]      
    mov rsi, [rsp + 16] 
    call strcat         
    pop rax             
    add rsp, 16         
    """

def pp_commande(ast):
    if ast.data == "assignation":
        lhs = ast.children[0].value
        rhs = pp_expression(ast.children[1])
        return f"{lhs} = {rhs};"
    if ast.data == "pass":
        return "pass\n"
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
    

def asm_commande(ast, env):  # N'oublie pas de passer l'environnement partout
    if ast.data == "assignation":
        lhs = ast.children[0].value
        type_var = env[lhs]

        # On récupère le type et le code de l'expression
        type_expr, asm_expr = asm_expression(ast.children[1], env)

        if type_var == "double" and type_expr == "int":
            return f"{asm_expr}\ncvtsi2sd xmm0, rax\nmovsd [{lhs}], xmm0\n"

        if type_var != type_expr:
            raise TypeError(
                f"Assignation invalide: '{lhs}' est de type {type_var}, "
                f"mais on lui assigne un {type_expr}"
            )

        if type_var == "int":
            return f"{asm_expr}\nmov [{lhs}], rax\n"
        elif type_var == "double":
            return f"{asm_expr}\nmovsd [{lhs}], xmm0\n"
        elif type_var.startswith("dict"):
            return f"{asm_expr}\nmov [{lhs}], rax\n"

    if ast.data == "pass":
        return "nop\n"

    if ast.data == "print":
        type_expr, asm_expr = asm_expression(ast.children[0], env)

        if type_expr == "int":
            return f"""{asm_expr}
                        mov rdi, format_entier
                        mov rsi, rax
                        mov rdi, [{dict_name}]
                        call set_in_dict
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
        lea rdi, [{dict_name}]
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
        test = asm_expression(ast.children[0], env)
        if test[0] != "int":
            raise TypeError("La condition n'est pas un booléen")

        cmd = asm_commande(ast.children[1], env)
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
                            movsd [{nom_var}], xmm0""")

    return "\n".join(res) + "\n"


def asm_decls_vars(ast):
    result = []
    for i in range(len(ast.children)):
        nom_var = ast.children[i].children[1].value
        if ast.children[i].children[0].value == "dict":
            result.append(f"{nom_var} dq 0 ; dict")
        else:
            result.append(f"{nom_var} dq 0 ; {ast.children[i].children[0].value}")
    return "\n".join(result) + "\n"

def pp_decl_vars(ast):
    result = []
    for i in range(len(ast.children)):
        nom_var = ast.children[i].children[1].value
        if ast.children[i].children[0].value == "dict":
            if len(ast.children[i].children) == 4:
                result.append(f"dict {nom_var}<{ast.children[i].children[2].value},{pp_types(ast.children[i].children[3])}>;")
        else:
            result.append(f"{ast.children[i].children[0].value} {nom_var};")
    return "\n".join(result) + "\n"

def pp_types(ast):
    if ast.children[0] in ["dict"]:
        return f"{ast.children[0]}<{ast.children[1].value},{pp_types(ast.children[2])}>"
    else:
        return ast.children[0].value
    
def pp_main(ast):
    vs = pp_liste_vars(ast.children[0])
    cmd = pp_commande(ast.children[1])
    ret = pp_expression(ast.children[2])
    return f"main({vs})\n    {cmd}\n    return ({ret});"




def asm_main(ast):
    ast_vars = ast.children[0]

    env = construire_env(ast_vars)
    decls = asm_decls_vars(ast_vars)
    vs = asm_liste_vars(ast_vars)
    cmd = asm_commande(ast.children[1], env)

    # Génération des constantes (const_float_0: dq 3.14)
    asm_consts = "\n".join(
        f"{label}: dq {valeur}" for valeur, label in constantes.items()
    )
    if asm_consts:
        decls += "\n" + asm_consts + "\n"

    # Déclaration des labels temporaires pour les dict_literal
    if temp_dict_labels:
        decls += "\n" + "\n".join(f"{lbl} dq 0" for lbl in temp_dict_labels) + "\n"

    # On récupère juste le code asm de l'expression de retour (index 1 du tuple)
    type_ret, ret_asm = asm_expression(ast.children[2], env)

    squelette = open("squelette.asm").read()
    dict_squelette = open("dict_squelette.asm").read()
    squelette = squelette.replace("DICT", dict_squelette) 
    squelette = squelette.replace("INIT_VARS", vs)
    squelette = squelette.replace("DECL_VARS", decls)
    squelette = squelette.replace("CONSTANTES", asm_consts)
    squelette = squelette.replace("COMMAND", cmd)
    squelette = squelette.replace("RETURN", ret_asm)
    squelette = squelette.replace("  ", "")

    return squelette


if __name__ == "__main__":
    src = open("source.c").read()
    t = grammaire.parse(src)
    with open("resultat.asm", "w") as f:
        f.write(asm_main(t))
