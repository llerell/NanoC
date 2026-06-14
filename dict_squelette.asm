init_dict:
    xor rax, rax
    ret

; Entrée: rdi = adresse du pointeur du dict (Attention: il nous faut l'adresse de la variable pour modifier sa tête si besoin !)
;         rsi = clé (64-bit)
;         rdx = valeur (64-bit)
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
    ; 2. Allocation via malloc
    mov rdi, 24
    
    mov r15, rsp
    and rsp, -16
    call malloc
    mov rsp, r15
    
    mov rbx, rax
    
    mov rax, [r12]          ; rax = ancien premier nœud
    mov [rbx], rax          ; nouveau_noeud->suivant = ancien premier nœud
    mov [rbx + 8], r13      ; nouveau_noeud->cle = clé
    mov [rbx + 16], r14     ; nouveau_noeud->valeur = valeur

    mov [r12], rbx

.fin_set:
    pop r14
    pop r13
    pop r12
    pop rbx
    pop rbp
    ret

; Variante de set_in_dict pour les clés de type str (comparaison par contenu via strcmp)
; Entrée: rdi = adresse du pointeur du dict
;         rsi = clé (pointeur vers chaîne)
;         rdx = valeur (64-bit)
set_in_dict_str:
    push rbp
    mov rbp, rsp
    push rbx
    push r12
    push r13
    push r14

    mov r12, rdi            ; r12 = adresse de la variable dict
    mov r13, rsi            ; r13 = clé recherchée (pointeur)
    mov r14, rdx            ; r14 = valeur à insérer

    mov rbx, [r12]          ; rbx = premier nœud de la liste
.boucle_recherche:
    cmp rbx, 0
    je .cle_non_trouvee

    mov rdi, [rbx + 8]      ; rdi = clé du nœud courant
    mov rsi, r13
    mov r15, rsp
    and rsp, -16
    call strcmp
    mov rsp, r15
    cmp rax, 0
    je .cle_trouvee

    mov rbx, [rbx]
    jmp .boucle_recherche

.cle_trouvee:
    mov [rbx + 16], r14
    jmp .fin_set

.cle_non_trouvee:
    mov rdi, 24

    mov r15, rsp
    and rsp, -16
    call malloc
    mov rsp, r15

    mov rbx, rax

    mov rax, [r12]
    mov [rbx], rax
    mov [rbx + 8], r13
    mov [rbx + 16], r14

    mov [r12], rbx

.fin_set:
    pop r14
    pop r13
    pop r12
    pop rbx
    pop rbp
    ret

; Entrée: rdi = adresse du dictionnaire (le pointeur lui-même)
;         rsi = clé recherchée
; Sortie: rax = valeur trouvée (clé absente => segfault volontaire)
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
    xor rax, rax
    mov rax, [rax]          ; clé absente : déréférencement de NULL -> segfault

; Variante de get_from_dict pour les clés de type str (comparaison par contenu via strcmp)
; Entrée: rdi = dictionnaire (tête de liste)
;         rsi = clé recherchée (pointeur vers chaîne)
; Sortie: rax = valeur trouvée (clé absente => segfault volontaire)
get_from_dict_str:
    push r12
    push r13
    push r14
    mov r12, rdi            ; r12 = nœud courant
    mov r13, rsi            ; r13 = clé recherchée
.boucle:
    cmp r12, 0
    je .non_trouve
    mov rdi, [r12 + 8]
    mov rsi, r13
    mov r14, rsp
    and rsp, -16
    call strcmp
    mov rsp, r14
    cmp rax, 0
    je .trouve
    mov r12, [r12]
    jmp .boucle
.trouve:
    mov rax, [r12 + 16]
    pop r14
    pop r13
    pop r12
    ret
.non_trouve:
    pop r14
    pop r13
    pop r12
    xor rax, rax
    mov rax, [rax]          ; clé absente : déréférencement de NULL -> segfault

; Entrée: rdi = dictionnaire (valeur, tête de liste)
;         rsi = clé recherchée
; Sortie: rax = adresse du champ valeur du nœud (clé absente => segfault volontaire)
get_addr_in_dict:
    mov rax, rdi            ; rax = nœud actuel
.boucle:
    cmp rax, 0
    je .non_trouve
    cmp [rax + 8], rsi
    je .trouve
    mov rax, [rax]          ; rax = nœud suivant
    jmp .boucle
.trouve:
    add rax, 16             ; rax = adresse du champ valeur
    ret
.non_trouve:
    xor rax, rax
    mov rax, [rax]          ; clé absente : déréférencement de NULL -> segfault

; Variante de get_addr_in_dict pour les clés de type str (comparaison par contenu via strcmp)
; Entrée: rdi = dictionnaire (tête de liste)
;         rsi = clé recherchée (pointeur vers chaîne)
; Sortie: rax = adresse du champ valeur du nœud (clé absente => segfault volontaire)
get_addr_in_dict_str:
    push r12
    push r13
    push r14
    mov r12, rdi            ; r12 = nœud courant
    mov r13, rsi            ; r13 = clé recherchée
.boucle:
    cmp r12, 0
    je .non_trouve
    mov rdi, [r12 + 8]
    mov rsi, r13
    mov r14, rsp
    and rsp, -16
    call strcmp
    mov rsp, r14
    cmp rax, 0
    je .trouve
    mov r12, [r12]
    jmp .boucle
.trouve:
    lea rax, [r12 + 16]
    pop r14
    pop r13
    pop r12
    ret
.non_trouve:
    pop r14
    pop r13
    pop r12
    xor rax, rax
    mov rax, [rax]          ; clé absente : déréférencement de NULL -> segfault

; Entrée: rdi = adresse du pointeur du dict (pour pouvoir modifier la tête)
;         rsi = clé à supprimer
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

; Variante de delete_from_dict pour les clés de type str (comparaison par contenu via strcmp)
; Entrée: rdi = adresse du pointeur du dict (pour pouvoir modifier la tête)
;         rsi = clé à supprimer (pointeur vers chaîne)
delete_from_dict_str:
    push r12
    push r13
    push r14
    push r15

    mov r12, rdi            ; r12 = adresse du pointeur "précédent"
    mov r13, [rdi]          ; r13 = nœud actuel
    mov r14, rsi            ; r14 = clé recherchée
.boucle:
    cmp r13, 0
    je .fin                 ; Clé non trouvée, rien à faire

    mov rdi, [r13 + 8]
    mov rsi, r14
    mov r15, rsp
    and rsp, -16
    call strcmp
    mov rsp, r15
    cmp rax, 0
    je .supprimer

    mov r12, r13            ; Le nœud actuel devient le "précédent"
    mov r13, [r13]          ; r13 = nœud suivant
    jmp .boucle

.supprimer:
    mov rdx, [r13]          ; rdx = nœud->suivant
    mov [r12], rdx          ; precedent->suivant = nœud->suivant (on court-circuite le nœud)
.fin:
    pop r15
    pop r14
    pop r13
    pop r12
    ret

; Entrée: rdi = dictionnaire
; Sortie: rax = nombre d'éléments
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

; Entrée: rdi = dictionnaire
;         rsi = index recherché (0-based)
; Sortie: rax = clé trouvée (ou 0 si index hors limites)
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