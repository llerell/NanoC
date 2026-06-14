# Compilateur nanoC par Lisa Lautier, Owen Le Ray et Vincent GUICHARD

## Utilisation

Pour installer les dépendances python, exécutez :
```shell
pip install -r requirements.txt
```

Pour lancer le compilateur, exécutez :
```shell
./script.sh
```
Cela va provoquer :
- l'exécution de main.py, qui va lui-même orchestrer :
    - La construction de la grammaire à partir du fichier `grammar.lark`.
    - Le chargement du fichier source à compiler, par défaut `source.c`
    - L'application de la grammaire au fichier source pour construire l'arbre syntaxique.
    - La vérification des types par TypeChecker, ainsi que la construction d'un index emplacements des variables sur la pile.
    - La création du code formaté par PrettyPrinter. Actuellement, on n'utilise pas le résultat, mais il est possible de l'imprimer.
    - La génération du code assembleur, que l'on sauvegarde dans le fichier `resultat.asm`
- L'exécution de `nasm` pour compiler le code assembleur en fichier exécutable.
- L'exécution du fichier exécutable.

## Répartition des tâches

- Lisa s'est occupé de l'implémentation des chaînes de caractères et des fonctions associées.
- Owen a ajouté les dictionnaires.
- Vincent a pris en charge les flottants l'organisation de l'architecture du code.

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
