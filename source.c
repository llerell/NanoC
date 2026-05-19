main(dict dico<int, int>, int x){
    x = 0;
    dico = {0: 1, 1: 2, 2: 3};
    dico[0] = 4;
    del dico[1];
    foreach (k in dico) {
        x = x + dico[k];
    }
    return dico;
}