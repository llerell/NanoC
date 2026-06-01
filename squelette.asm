extern printf, atoi, atof
section .data
argv: dq 0
format_entier: db "%lld", 10, 0
format_flottant: db "%lf", 10, 0
DECL_VARS
global main
section .text
DICT
main:
push rbp
mov rbp, rsp
mov [argv], rsi
INIT_VARS
COMMAND 
RETURN
pop rbp
ret