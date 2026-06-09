import unittest
import lark
import textwrap
import PrettyPrinter
import TypeChecker
import CodeGenerator


class TestCompilation(unittest.TestCase):
    def setUp(self):
        with open("grammar.lark", "r") as f:
            self.grammaire = lark.Lark(f.read(), start="main")

    def _run_pipeline(self, source: str):
        """Méthode utilitaire qui exécute toute la chaîne de compilation sur un code source"""
        # 1. Parsing
        tree = self.grammaire.parse(source)

        # 2. PrettyPrinter
        pp = PrettyPrinter.PrettyPrinter()
        result = pp.main(tree)
        self.assertEqual(result, source)

        # 3. TypeChecker
        tc = TypeChecker.TypeChecker()
        tc.main(tree)

        # 4. CodeGenerator
        cg = CodeGenerator.CodeGenerator(tc.node_types, tc.var_offsets, tc.stack_size)
        return cg.main(tree)

    def test_valid_programs(self):
        """Teste une série de programmes valides qui doivent compiler sans erreur"""
        programmes_valides = [
            """
            main() {
            pass
            }
            """,
            """
            main(int i, double d, str s) {
            pass
            }
            """,
            """
            main(int i) {
            return i;
            }
            """,
            """
            main(int i) {
            print(i);
            }
            """,
            """
            main(int i) {
            int x = 0;
            x = i + x - 5 * 7 / 3 % 5;
            print(x);
            }
            """,
            """
            main(int i, int x) {
            x = !i & x | i ^ x;
            print(x);
            }
            """,
            """
            main(int i, double d) {
            i = int(d);
            }
            """,
            """
            main(double d) {
            d = 3.0 / 4 * 5 + 2 - 4.0;
            }
            """,
            """
            main() {
            if (1 > 0) {
            print(1);
            }
            }
            """,
            """
            main() {
            while (1 > 0) {
            print(1);
            }
            }
            """
        ]

        for source in programmes_valides:
            source_propre = textwrap.dedent(source).strip() + "\n"

            with self.subTest(code=source_propre):
                self._run_pipeline(source_propre)

    def test_unvalid_programs(self):
        """Teste une série de programmes valides qui doivent déclencher une erreur"""
        programmes_invalides = [
            """
            main() {
            }
            """,
            """
            main() {
            i = 2;
            }
            """,
            """
            main(int i) {
            return x;
            }
            """,
            """
            main(double d) {
            d = 5.0 % 4.0;
            }
            """,
            """
            main(double d) {
            d = !1.0;
            print(x);
            }
            """,
            """
            main(int i, double d) {
            i = double(d);
            }
            """,
            """
            main() {
            if (1.0) {
            print(1);
            }
            }
            """,
            """
            main() {
            while (true) {
            print(1);
            }
            }
            """
        ]

        for source in programmes_invalides:
            source_propre = textwrap.dedent(source).strip() + "\n"

            with self.subTest(code=source_propre):
                with self.assertRaises(Exception):
                    self._run_pipeline(source_propre)

if __name__ == "__main__":
    unittest.main()
