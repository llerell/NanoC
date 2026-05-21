main(int x, double y, double z){
    z = 1;
    x = 1;
    y = 4;
    while(x){
        z = z * 2;
        x = x - 1;
    }
    z = z / 3;
    print(z);
    return y;
}