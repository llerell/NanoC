extern printf, atoi, atof
section .data
argv: dq 0
format_entier: db "%lld", 10, 0
format_flottant: db "%lf", 10, 0

section .text
global init_dict
global set_in_dict
global get_from_dict
global delete_from_dict
global dict_get_size
global dict_get_key_by_index

; ==============================================================================
; init_dict
; Entrée: Rien
; Sortie: rax = Pointeur vers le dictionnaire initialisé (ici un pointeur NULL)
; ==============================================================================
init_dict:
    xor rax, rax            ; Un dictionnaire vide est simplement représenté par un pointeur NULL (0)
    ret

; ==============================================================================
; set_in_dict
; Entrée: rdi = adresse du pointeur du dict (Attention: il nous faut l'adresse de la variable pour modifier sa tête si besoin !)
;         rsi = clé (64-bit)
;         rdx = valeur (64-bit)
; ==============================================================================
set_in_dict:
    push rbp
    mov rbp, rsp
    push rbx
    push r12
    push r13
    push r14

    mov r12, rdi            ; r12 = adresse de la variable dict (ex: [mon_dict])
    mov r13, rsi            ; r13 = clé recherchée
    mov r14, rdx            ; r14 = valeur à insérer

    ; 1. Parcourir la liste pour voir si la clé existe déjà
    mov rbx, [r12]          ; rbx = premier nœud de la liste
.boucle_recherche:
    cmp rbx, 0
    je .cle_non_trouvee     ; Si rbx == 0, fin de la liste
    
    cmp [rbx + 8], r13      ; Comparaison avec la clé du nœud actuel
    je .cle_trouvee
    
    mov rbx, [rbx]          ; rbx = nœud suivant
    jmp .boucle_recherche

.cle_trouvee:
    mov [rbx + 16], r14     ; Mise à jour de la valeur
    jmp .fin_set

.cle_non_trouvee:
    ; 2. Allocation d'un nouveau nœud (24 octets) via sys_brk
    ; Demande de la position actuelle du break
    mov rax, 12             ; syscall: sys_brk
    xor rdi, rdi            ; 0 pour obtenir l'adresse actuelle
    syscall
    
    mov rbx, rax            ; rbx = adresse du nouveau nœud
    
    ; Calcul du nouveau break (adresse actuelle + 24 octets)
    mov rdi, rax
    add rdi, 24
    mov rax, 12             ; syscall: sys_brk
    syscall                 ; rax contient maintenant la nouvelle limite si succès

    ; 3. Remplissage du nouveau nœud
    mov rax, [r12]          ; rax = ancien premier nœud
    mov [rbx], rax          ; nouveau_noeud->suivant = ancien premier nœud
    mov [rbx + 8], r13      ; nouveau_noeud->cle = clé
    mov [rbx + 16], r14     ; nouveau_noeud->valeur = valeur

    ; 4. Mettre à jour la tête du dictionnaire
    mov [r12], rbx

.fin_set:
    pop r14
    pop r13
    pop r12
    pop rbx
    pop rbp
    ret

; ==============================================================================
; get_from_dict
; Entrée: rdi = adresse du dictionnaire (le pointeur lui-même)
;         rsi = clé recherchée
; Sortie: rax = valeur trouvée (ou 0 si non trouvée)
; ==============================================================================
get_from_dict:
    mov rax, rdi            ; rax = nœud actuel
.boucle:
    cmp rax, 0
    je .non_trouve
    cmp [rax + 8], rsi
    je .trouve
    mov rax, [rax]          ; rax = nœud suivant
    jmp .boucle
.trouve:
    mov rax, [rax + 16]     ; rax = valeur
    ret
.non_trouve:
    xor rax, rax            ; Retourne 0 par défaut
    ret

; ==============================================================================
; delete_from_dict
; Entrée: rdi = adresse du pointeur du dict (pour pouvoir modifier la tête)
;         rsi = clé à supprimer
; ==============================================================================
delete_from_dict:
    mov rcx, rdi            ; rcx = adresse du pointeur "précédent" (commence à l'adresse de la tête)
    mov rax, [rdi]          ; rax = nœud actuel
.boucle:
    cmp rax, 0
    je .fin                 ; Clé non trouvée, rien à faire
    
    cmp [rax + 8], rsi
    je .supprimer
    
    mov rcx, rax            ; Le nœud actuel devient le "précédent"
    mov rax, [rax]          ; rax = nœud suivant
    jmp .boucle

.supprimer:
    mov rdx, [rax]          ; rdx = nœud->suivant
    mov [rcx], rdx          ; precedent->suivant = nœud->suivant (on court-circuite le nœud)
.fin:
    ret

; ==============================================================================
; dict_get_size
; Entrée: rdi = dictionnaire
; Sortie: rax = nombre d'éléments
; ==============================================================================
dict_get_size:
    xor rax, rax            ; compteur = 0
.boucle:
    cmp rdi, 0
    je .fin
    inc rax
    mov rdi, [rdi]          ; rdi = nœud suivant
    jmp .boucle
.fin:
    ret

; ==============================================================================
; dict_get_key_by_index
; Entrée: rdi = dictionnaire
;         rsi = index recherché (0-based)
; Sortie: rax = clé trouvée (ou 0 si index hors limites)
; ==============================================================================
dict_get_key_by_index:
    xor rcx, rcx            ; index_courant = 0
.boucle:
    cmp rdi, 0
    je .hors_limites
    cmp rcx, rsi
    je .trouve
    inc rcx
    mov rdi, [rdi]          ; rdi = nœud suivant
    jmp .boucle
.trouve:
    mov rax, [rdi + 8]      ; rax = clé
    ret
.hors_limites:
    xor rax, rax
    ret
section .data
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