main(x,y,z){
    z = 0;
    x = 1;
    y = 1;
    while(x < 6){
        z = z + 1 * 2;
        x = x + 1;
        y = y * 2;
    }
    print(y);
    return y;
}