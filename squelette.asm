extern printf, atoi, atof
section .data
argv: dq 0
format_entier: db "%lld\n", 0
format_flottant: db "%lf\n", 0

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