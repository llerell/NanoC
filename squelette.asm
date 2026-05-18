extern printf, atoi
section .data
argv: dq 0
format: db "%lld\n", 0
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
mov rdi, rax
xor rax, rax
call printf
pop rbp
ret