"""__version__ (src/rudi_commune_starterkit/__init__.py) et pyproject.toml sont tenus à
jour manuellement ensemble (pas de résolution via importlib.metadata — voir le
docstring de __init__.py) : ce test détecte un oubli de synchronisation à la release."""
import re
import unittest
from pathlib import Path

from rudi_commune_starterkit import __version__


class TestVersionSynchroniseeAvecPyproject(unittest.TestCase):
    def test_versions_identiques(self):
        chemin_pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        texte = chemin_pyproject.read_text(encoding="utf-8")
        m = re.search(r'^version\s*=\s*"([^"]+)"', texte, re.MULTILINE)
        self.assertIsNotNone(m, "version absente de pyproject.toml")
        self.assertEqual(__version__, m.group(1))
