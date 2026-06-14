main() {

    // ---- precedence: == binds tighter than | & ^, which bind tighter than && || ----
    print(1 == 1 && 2 | 4 == 4);
    print(2 + 3 * 4 - 10 / 2 % 3);
    print(!(0 == 1));

    // ---- implicit int -> double promotion in comparisons/arithmetic ----
    print(1 == 1.0);
    print(1 + 1.5);

    // ---- int <-> double conversions ----
    double pi = 3.14159;
    int approx = int(pi * 100.0);
    print(approx);
    print(double(approx) / 100.0);

    // ---- strings: concat, len, charAt, atoi ----
    str greeting = "Hello, " + "World!";
    print(greeting);
    print(len(greeting));
    print(charAt(greeting, 7));
    print(atoi("-123") + atoi("42"));

    // ---- 3 levels of nested dicts, read + write ----
    dict<int,dict<int,dict<int,int>>> cube = {1: {2: {3: 12345}}};
    print(cube[1][2][3]);
    cube[1][2][3] = 999;
    print(cube[1][2][3]);

    // ---- aliasing: dict variables hold a shared pointer, not a copy ----
    dict<int,int> original = {1: 100};
    dict<int,int> alias = original;
    alias[1] = 777;
    print(original[1]);

    // ---- string-keyed dict: equality is by content (strcmp), not pointer ----
    dict<str,int> wordcount = {};
    wordcount["foo" + "bar"] = 7;
    print(wordcount["foobar"]);

    // ---- double-keyed dict ----
    dict<double,str> pies = {};
    pies[3.14] = "tau/2";
    print(pies[3.14]);

    // ---- while loop ----
    int i = 0;
    int sum = 0;
    while (i < 5) {
        sum = sum + i;
        i = i + 1;
    }
    print(sum);

    // ---- foreach over a dict ----
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

    // ---- del, then access the now-missing key: documented "Crash silencieux" ----
    del squares[2];
    print(squares[2]);
}
