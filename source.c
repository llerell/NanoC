main(int x, int y, double z){
    z = 1.0;
    x = 1;
    while(x){
        z = z * 2.0;
        x = x - 1;
    }
    print(z);
    return y;
}