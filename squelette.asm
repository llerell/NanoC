default rel

extern printf, atoi, atof
section .data
argv: dq 0
format_entier: db "%lld", 0
format_flottant: db "%lf", 0
format_retour: db 10, 0 ; 10="\n", 0="\0"

DECL_VARS

section .rodata
CONSTANTES

global main
section .text
main:
push rbp
mov rbp, rsp
mov [argv], rsi
INIT_VARS
COMMAND 

mov rdi, format_retour
xor rax, rax
call printf

RETURN
pop rbp
ret