extern printf, atoi, atof, strlen, malloc, strcpy, strcat 
section .data
argv: dq 0
format_entier: db "%lld", 10, 0
format_flottant: db "%lf\n", 0
format_chaine: db "%s", 10, 0

DECL_VARS
global main
section .text
main:
push rbp
mov rbp, rsp
mov [argv], rsi
INIT_VARS
COMMAND 
RETURN
pop rbp
ret