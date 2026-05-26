extern printf, atoi, atof
section .data
argv: dq 0
format_entier: db "%lld", 0
format_flottant: db "%lf", 0

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