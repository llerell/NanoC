main() {

    print(1 == 1 && 2 | 4 == 4);
    print(2 + 3 * 4 - 10 / 2 % 3);
    print(!(0 == 1));

    str greeting = "Hello, " + "World!";
    print(greeting);
    print(len(greeting));
    print(charAt(greeting, 7));
    print(atoi("-123") + atoi("42"));


    dict<int,dict<int,dict<int,int>>> cube = {1: {2: {3: 12345}}};
    print(cube[1][2][3]);
    cube[1][2][3] = 999;
    print(cube[1][2][3]);


    dict<int,int> original = {1: 100};
    dict<int,int> alias = original;
    alias[1] = 777;
    print(original[1]);


    dict<str,int> wordcount = {};
    wordcount["foo" + "bar"] = 7;
    print(wordcount["foobar"]);


    dict<double,str> pies = {};
    pies[3.14] = "tau/2";
    print(pies[3.14]);


    int i = 0;
    int sum = 0;
    while (i < 5) {
        sum = sum + i;
        i = i + 1;
    }
    print(sum);


    dict<int,int> squares = {};
    squares[0] = 0;
    squares[1] = 1;
    squares[2] = 4;
    squares[3] = 9;
    int total = 0;
    foreach(k in squares) {
        total = total + squares[k];
    }
    print(total);


    del squares[2];
    print(squares[2]);
}
