"""Tenu à jour manuellement en même temps que ``version`` dans ``pyproject.toml`` —
voir ``tests/test_version.py`` pour la vérification de cohérence entre les deux.
Pas de résolution via ``importlib.metadata`` : l'exécutable PyInstaller (voir
``packaging/``) n'embarque pas les métadonnées de paquet sans ``--copy-metadata``,
ce qui ferait échouer silencieusement ``--version`` dans le seul contexte où un
agent municipal non technique pourrait avoir besoin de le vérifier."""

__version__ = "0.7.8"
