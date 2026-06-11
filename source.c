main() {

    // oui ça fonctionne
    int v = 0;
    int n = 0;
    dict<int,int> mon_dict = {10: 100, 20: 200, 30: 300};
    
    mon_dict[40] = 400 + 3 / 20 - 8 + 2 * 2;
    mon_dict[20] = !222 & 1 | 2;

    print(mon_dict[20]);
    print(mon_dict[30]);
    print(mon_dict[40]);

    dict<int,dict<int,int>> dico2 = {2: {10:100}};

        
    dico2[0] = {10:100};
    dico2[1] = mon_dict;

    //print(dico2[1][20]);
    
    
    // foreach(cle_courante in mon_dict) {
    //     valeur_courante = mon_dict[cle_courante];
    //     print(valeur_courante);
    //     v = v + valeur_courante;
    //     print(v);
    // }
}