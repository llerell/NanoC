main(int x, double y, double z){
    /*
    début de la fonction
    */
    z = 1e-3;
    x = 1;
    y = 4e-5;
    while(x){
        z = z * 2;
        x = x - 1;
    }
    z = z / 3;
    x = x & 1 | 0;
    print(35.0/3);
    // bonsoir
    return y;
}