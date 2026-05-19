#!/bin/bash
# run debut
python3.14 nanoC.py &&
nasm -f elf64 resultat.asm &&
gcc -no-pie resultat.o -o resultat.exe &&
./resultat.exe
