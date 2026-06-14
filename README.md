install dependencies:
pip install -r requirements.txt

To run the compiler :

run chmod +x script.sh once to make the bash script executable

run ./script.sh to compile source.c. 


1. ce qui a été fait et par qui
Lisa : chaîne de caractère et caractères

2. Comment utiliser le compilateur

3. Hypothèses sur le langage

4. Principes mis en oeuvre 

5. Note de groupe : parfait pour l'instant
## Dictionnaires

Un dictionnaire se déclare avec `dict<TypeClé, TypeValeur>`. `TypeClé` doit
être `int`, `double` ou `str`. `TypeValeur` peut être `int`, `double`, `str`,
ou un autre `dict<...>` (dictionnaires imbriqués).

```c
dict<int, int> scores = {};
dict<str, int> ages = {"alice": 30, "bob": 25};

scores[1] = 100;
print(scores[1]);   // 100
```

### Dictionnaires imbriqués

```c
dict<int, dict<int, int>> grille = {1: {2: 42}};
print(grille[1][2]);   // 42

grille[1][2] = 100;
```

Pour écrire dans un dictionnaire imbriqué supplémentaire (comme `grille[3]'), il faut d'abord initialiser ledit dictionnaire

```c
grille[3] = {};
grille[3][4] = 7;
```

### Suppression

```c
del scores[1];
```

Accéder à une clé absente **fait
planter le programme** (segfault). Assurez-vous que la clé existe avant de la lire.

### Parcours

```c
foreach (cle in scores) {
    print(scores[cle]);
}
```

### Affectation

L'affectation d'un dictionnaire donne un pointeur vers les mêmes données.

```c
dict<int,int> a = {1: 1};
dict<int,int> b = a;
b[1] = 2;
print(a[1]);   // 2, car a et b partagent le même dictionnaire
```

### Conversion de clés ou de valeurs

Contrairement aux opérations arithmétiques (`1 + 1.5` convertit
automatiquement le `1` en `double`), les clés et les valeurs d'un
dictionnaire n'acceptent **aucune conversion implicite** : le type doit
correspondre exactement à celui déclaré.

```c
dict<double,double> d = {};
d[1] = 2.0;        // erreur de compilation : clé de type int, attendu double

dict<int,int> e = {1: 1};
e[1] = 2.0;        // erreur de compilation : valeur de type double, attendu int
```

Pour une clé ou une valeur `double`, il faut écrire un littéral avec un point
décimal (`d[1.0] = 2.0;`). 
