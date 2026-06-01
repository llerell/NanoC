import lark

grammaire = lark.Lark(
    r"""
IDENTIFIER: /[a-zA-Z_][a-zA-Z_0-9]*/
STRING : /"[^"]*"/
CHAR : /'[^']'/
OPBIN: /<=|>=|==|!=|[+\-*\/<>%&|^]/
TYPE : "int" | "double" | "str"
decl : TYPE IDENTIFIER
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
%ignore /\/\/[^\n\r]*/
%ignore /\/\*[\s\S]*?\*\//
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
        type_var = decl.children[0].value # "int"  "double" ou "str"
        nom_var = decl.children[1].value  
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
    eg = f"{pp_expression(ast.children[0])}"
    op = ast.children[1].value
    ed = f"{pp_expression(ast.children[2])}"
    return f"{eg} {op} {ed}"


def asm_expression(ast, env: dict) -> tuple[str, str]:

    if ast.data in ("entier", "double"):
        type_lit = ast.data
        valeur = ast.children[0].value

        # vérification de la présence de la constante
        if (type_lit, valeur) not in constantes:
            label = f"const_{type_lit}_{len(constantes)}"
            constantes[(type_lit, valeur)] = label
        else:
            label = constantes[(type_lit, valeur)]

        if type_lit == "entier":
            return "int", f"mov rax, [{label}]\n"

        if type_lit == "double":
            return "double", f"movsd xmm0, [{label}]\n"

    if ast.data == "variable":
        nom = ast.children[0].value
        type_var = env[nom]

        if type_var == "int":
            return "int", f"mov rax, [{nom}]\n"
        elif type_var == "double":
            return "double", f"movsd xmm0, [{nom}]\n"
        elif type_var=="str":
            return "str", f"mov rax, [{nom}]\n"
    if ast.data == "chaine":
        lbl = f"lit_{next(compteur)}"
        valeur = ast.children[0].value
        constantes[lbl] = valeur
        return "str", f"mov rax, {lbl}\n"
    #il y aura écrit lit_1 : "abc" dans .data, NASM regardera où en est son compteur interne, l'adresse correspondante est associée à lit_1
    #plus tard quand il voit mov rax, lit_1 il remplace lit_1 par l'adresse associée où a été stockée "abc"
        
    if ast.data == "caractere":
        return "int", f"mov rax, {ast.children[0].value}\n"
    #un carac est vu comme sa valeur ascii par le processeur

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

    if ast.data=="atoi":
        # On évalue ce qu'il y a dans les parenthèses
        type_expr, code = asm_expression(ast.children[0],env) #si atoi("123"), dans code il y a l'asm qui met l'adresse de "123" dans rax
        # On génère le code : on met l'adresse de la chaîne dans rdi, puis on appelle atoi
        return "int", f"""{code}
                          mov rdi, rax
                          call atoi
                          """
    if ast.data=="len" :
        type_expr, code = asm_expression(ast.children[0],env) #même chose
        return "int", f"""{code}
                  mov rdi, rax
                  call strlen
                  """    
    if ast.data == "charat":
        str_asm = asm_expression(ast.children[0],env)[1]
        idx_asm = asm_expression(ast.children[1],env)[1]
        # On évalue d'abord l'index qu'on pousse sur la pile, puis l'adresse de la chaîne
        code_charat = idx_asm + "push rax\n" + str_asm + "pop rbx\nmovzx rax, byte [rax + rbx]\n"
        return "int", code_charat
    #byte : ne lire qu'un seul octet (un carac fait 8bits)
    # au final, rax contient la valeur numérique du caractère demandé

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

        if type_var == "int" or type_var=="str":
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
        elif type_expr == "str" :
            return f"""{asm_expr}
                        mov rdi, format_chaine
                        mov rsi, rax
                        xor rax, rax
                        call printf
                    """

    if ast.data == "sequence":
        cg = asm_commande(ast.children[0], env)
        cd = asm_commande(ast.children[1], env)
        return f"{cg}{cd}"

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
    return ", ".join((v.value for v in ast.children))

def asm_liste_vars(ast) -> str:
    res = []
    for i in range(len(ast.children)):
        type_var = ast.children[i].children[0].value
        nom_var = ast.children[i].children[1].value

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
        if type_var == "str":
            res.append(f"""mov rdi, [argv]
                        add rdi, {(i+1)*8}
                        mov rax, [rdi]
                        mov [{nom_var}], rax""")


    return "\n".join(res) + "\n"


def asm_decls_vars(ast):
    # TODO pour l'instant, on part du principe qu'on a des variables de taille 8
    # ast.children[i].children[0] contient le type
    return "\n".join(
        f"{ast.children[i].children[1].value}: dq 0" for i in range(len(ast.children))
    )


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
        f"{label}: dq {valeur[1]}" for valeur, label in constantes.items()
    )

    # On récupère juste le code asm de l'expression de retour (index 1 du tuple)
    type_ret, ret_asm = asm_expression(ast.children[2], env)

    squelette = open("squelette.asm").read()
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
