main(int argument, dict mon_dict<int,int>,
    int cle_courante,
    int valeur_courante,
    int k, 
    int v) {

    v = 0;
    mon_dict = {10: 100, 20: 200, 30: 300};
    
    mon_dict[40] = 400;
    mon_dict[20] = 222;
    
    del mon_dict[30];
    
    print(valeur_courante);
    
    foreach(cle_courante in mon_dict) {
        valeur_courante = mon_dict[cle_courante];
        print(valeur_courante);
        v = v + valeur_courante;
        print(v);
    }
    
    return 0;
}