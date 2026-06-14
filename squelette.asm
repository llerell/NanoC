default rel

extern printf, atoi, atof, strlen, malloc, strcpy, strcat, strcmp
section .data
argv: dq 0
format_entier: db "%lld", 10, 0
format_flottant: db "%lf", 10, 0
format_chaine: db "%s", 10, 0

section .rodata
CONSTANTES

global main
section .text
DICT

main:
push rbp
mov rbp, rsp
mov [argv], rsi
INIT_VARS
COMMAND

end_main:
leave
ret