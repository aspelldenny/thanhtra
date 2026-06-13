"""Unit tests for deterministic pre-scan logic (stdlib unittest, zero-dep)."""

import tempfile
import unittest
from pathlib import Path

from thanhtra.core import prescan


class ClassifyFileTest(unittest.TestCase):
    def test_source(self):
        self.assertEqual(prescan.classify_file("app/api/users.py"), "source")

    def test_documentation(self):
        self.assertEqual(prescan.classify_file("README.md"), "documentation")

    def test_secret_config(self):
        self.assertEqual(prescan.classify_file(".env"), "secret-config")

    def test_dependency(self):
        dep = next(iter(prescan.DEPENDENCY_FILES))
        self.assertEqual(prescan.classify_file(dep), "dependency")


class MaskTest(unittest.TestCase):
    def test_long_value_keeps_only_edges(self):
        self.assertEqual(prescan.mask("sk_live_ABCDEFGH1234"), "sk_l...1234")

    def test_short_value_is_hidden(self):
        self.assertEqual(prescan.mask("short"), "***hort")


class LanguageCountTest(unittest.TestCase):
    def test_counts_by_extension(self):
        py_lang = next(lang for lang, exts in prescan.LANG_EXTS.items() if ".py" in exts)
        counts = prescan.language_counts(["a.py", "b.py", "notes.unknownext"])
        self.assertEqual(counts.get(py_lang), 2)


class VendoredTest(unittest.TestCase):
    def test_vendored_dir_is_skipped(self):
        part = next(iter(prescan.VENDORED_PARTS))
        self.assertTrue(prescan.is_vendored(Path(f"{part}/inner/file.js")))

    def test_source_dir_is_not_vendored(self):
        self.assertFalse(prescan.is_vendored(Path("src/app.py")))


class HotspotTest(unittest.TestCase):
    """Hotspots are a high-recall net; these assert the regex layer fires
    where it should and stays quiet on the safe counterpart."""

    def _hotspots(self, filename, content):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / filename).write_text(content, encoding="utf-8")
            return prescan.collect_hotspots(root, [filename], max_per_rule=50)

    def test_insecure_randomness_fires(self):
        h = self._hotspots("token.ts", "export const t = Math.random().toString(36);\n")
        self.assertTrue(h.get("INSECURE-RANDOMNESS"))

    def test_insecure_randomness_clean_on_csprng(self):
        h = self._hotspots(
            "token.ts",
            "import { randomBytes } from 'crypto';\nconst t = randomBytes(32).toString('hex');\n",
        )
        self.assertFalse(h.get("INSECURE-RANDOMNESS"))

    def test_exception_mishandling_fires_on_broad_catch(self):
        h = self._hotspots("auth.py", "try:\n    verify(token)\nexcept Exception:\n    pass\n")
        self.assertTrue(h.get("EXCEPTION-MISHANDLING"))

    def test_exception_mishandling_clean_on_specific_catch(self):
        h = self._hotspots(
            "auth.py",
            "try:\n    verify(token)\nexcept InvalidToken:\n    return False\n",
        )
        self.assertFalse(h.get("EXCEPTION-MISHANDLING"))


if __name__ == "__main__":
    unittest.main()
