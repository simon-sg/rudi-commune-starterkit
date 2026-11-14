"""Primitives de sécurité pour les identifiants du nœud RUDI cible.

Module autonome (aucune dépendance au reste du projet) : validation d'URL, lecture de
mot de passe sans écho, fichier de configuration en clair à permissions restreintes,
trousseau système (``keyring``) avec détection de backend en clair.
"""

from __future__ import annotations

import getpass
import json
import os
import re
import stat
import subprocess
import sys
import warnings
from urllib.parse import urlsplit

import keyring

_HOTES_LOCAUX = ("localhost", "127.0.0.1", "::1")


class UrlNoeudNonSecurisee(ValueError):
    """URL de nœud en http:// sans autorisation explicite d'usage local."""


def valider_url_noeud(url: str, *, autoriser_http_local: bool = False) -> str:
    """Refuse une URL ``http://`` (identifiants en clair sur le réseau), sauf si
    ``autoriser_http_local=True`` ET que l'hôte est localhost/127.0.0.1/::1.
    ``https://`` est toujours accepté. Retourne l'URL sans le ``/`` de fin."""
    url = url.strip()
    morceaux = urlsplit(url)
    if morceaux.scheme == "https":
        return url.rstrip("/")
    if morceaux.scheme == "http":
        if autoriser_http_local and morceaux.hostname in _HOTES_LOCAUX:
            return url.rstrip("/")
        raise UrlNoeudNonSecurisee(
            f"URL {url!r} en http:// refusée (identifiants envoyés en clair sur le "
            "réseau) — utiliser https://, ou autoriser_http_local=True pour un usage "
            "local type localhost/127.0.0.1."
        )
    raise UrlNoeudNonSecurisee(f"URL {url!r} : schéma attendu http(s), reçu {morceaux.scheme!r}.")


_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def email_valide(adresse: str) -> bool:
    """Validation de forme basique — pas une validation RFC complète, juste assez pour
    éviter une saisie clairement fausse avant de l'envoyer comme contact Rudi."""
    return bool(_RE_EMAIL.match(str(adresse).strip()))


_TLD_RESERVES = ("local", "test", "example", "invalid")


def email_suspect(adresse: str) -> str | None:
    """Avertissement d'hygiène — jamais un blocage — si le domaine de ``adresse`` se
    termine par un TLD réservé RFC 2606/6761 (``.local``, ``.test``, ``.example``,
    ``.invalid``) : jamais routable publiquement, donc jamais un vrai contact.

    Un domaine ``.local`` a été corrélé une fois à un ``403 Forbidden`` Dataverse
    silencieux (le `403` a disparu quand le contact a été changé) — hypothèse de
    diagnostic forte mais **non prouvée** au niveau Dataverse ; traité ici comme un
    signal d'hygiène visible, pas comme une garantie, donc pas un échec bloquant.

    Retourne le message d'avertissement si suspect, ``None`` sinon (y compris pour une
    adresse déjà mal formée — c'est le rôle de :func:`email_valide`, pas de celle-ci)."""
    adresse = str(adresse).strip()
    if "@" not in adresse:
        return None
    domaine = adresse.rsplit("@", 1)[1].lower()
    tld = domaine.rsplit(".", 1)[-1] if "." in domaine else domaine
    if tld in _TLD_RESERVES:
        return (
            f"domaine {domaine!r} suspect : TLD réservé {tld!r} (RFC 2606/6761), jamais "
            "routable publiquement."
        )
    return None


class AbsenceTerminalError(RuntimeError):
    """Pas de TTY (pipe/CI), ou TTY présent mais incapable de masquer la saisie
    (``termios`` en échec, ex. ENOTTY) : dans les deux cas, ``getpass`` afficherait
    le mot de passe en clair ou bloquerait."""


def lire_mot_de_passe(invite: str = "Mot de passe : ") -> str:
    """Lit un mot de passe sans écho. Lève :class:`AbsenceTerminalError` si
    ``sys.stdin`` n'est pas un terminal, ou si le terminal est présent mais que
    ``getpass`` ne peut pas en désactiver l'écho — plutôt que de le laisser dégrader
    silencieusement vers une saisie affichée en clair.

    Volontairement multiplateforme, pas seulement le cas Linux qui l'a révélé
    (binaire PyInstaller, 2026-11-14 : ``/dev/tty`` s'ouvre mais
    ``termios.tcgetattr`` échoue avec ENOTTY, non détecté par ``sys.stdin.isatty()``
    seul) : sous Windows, ``getpass.win_getpass`` dégrade de la même façon (écho en
    clair, ``GetPassWarning``) dès que ``sys.stdin`` a été substitué (terminal/
    lanceur non standard, ex. Git Bash/MSYS2) même si ``isatty()`` reste vrai — même
    protection, même raison : jamais d'écho silencieux, quitte à devoir utiliser
    ``--rudi-conf``/``--utiliser-trousseau`` dans ce cas plutôt que l'assistant."""
    if not sys.stdin.isatty():
        raise AbsenceTerminalError(
            "Aucun terminal disponible pour saisir un mot de passe sans écho "
            "(invocation depuis un pipe/CI ?) — utiliser --rudi-conf ou "
            "--utiliser-trousseau en mode scriptable."
        )
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            return getpass.getpass(invite)
        except getpass.GetPassWarning as e:
            raise AbsenceTerminalError(
                f"Terminal incapable de masquer la saisie du mot de passe ({e}) — "
                "utiliser --rudi-conf ou --utiliser-trousseau en mode scriptable."
            ) from e


def _restreindre_acces_windows(chemin: str) -> bool:
    """Restreint l'accès à ``chemin`` à l'utilisateur Windows courant via ``icacls``
    (outil natif, pas de dépendance ``pywin32``). NTFS n'a pas de permissions POSIX :
    ``os.chmod``/``os.stat().st_mode`` n'y pilotent que l'attribut lecture seule, jamais
    une restriction d'accès par compte — ``os.chmod(chemin, 0o600)` y est donc un no-op
    silencieux pour la confidentialité, ce qui a été découvert via un échec de test sous
    Windows (CI) le 2026-11-11, pas anticipé à l'écriture initiale de ce module.
    N'échoue jamais (ni exception, ni faux positif) : retourne ``False`` et avertit si
    ``icacls`` est indisponible ou échoue, plutôt que de laisser croire que le fichier
    est protégé — y compris si ``icacls`` lui-même est introuvable (``FileNotFoundError``,
    poste verrouillé/PATH corrompu), capturé explicitement plutôt que de laisser
    l'exception remonter jusqu'à l'appelant."""
    utilisateur = os.environ.get("USERNAME", "")
    if not utilisateur:
        print(
            f"[sécurité] Attention : utilisateur Windows courant introuvable "
            f"(variable USERNAME absente), {chemin} reste avec les permissions par défaut."
        )
        return False
    try:
        resultat = subprocess.run(
            ["icacls", chemin, "/inheritance:r", "/grant:r", f"{utilisateur}:F"],
            capture_output=True, text=True, check=False,
        )
    except OSError as exc:
        print(
            f"[sécurité] Attention : impossible d'exécuter icacls ({exc}) — "
            f"{chemin} reste avec les permissions par défaut."
        )
        return False
    if resultat.returncode != 0:
        print(
            f"[sécurité] Attention : restriction des permissions de {chemin} via icacls "
            f"a échoué ({resultat.stderr.strip()}) — le fichier peut rester lisible par "
            "d'autres comptes."
        )
        return False
    return True


def ecrire_conf_fichier(chemin: str, conf: dict) -> None:
    """Écrit ``conf`` en JSON dans ``chemin`` avec un accès restreint à l'utilisateur
    courant. Sous POSIX : permissions ``0600`` dès la création (``os.open`` avec
    ``O_CREAT|O_WRONLY|O_TRUNC``, pas ``chmod`` après coup, qui laisserait une fenêtre
    avec des permissions plus larges) ; si le fichier existait déjà avec des permissions
    plus larges, les corrige en plus via ``os.chmod``. Sous Windows (NTFS, pas de
    permissions POSIX) : voir :func:`_restreindre_acces_windows` — le fichier est créé
    vide puis restreint *avant* d'y écrire le contenu sensible, pour ne jamais laisser le
    JSON en clair sur disque avec des permissions par défaut, même un court instant."""
    dossier = os.path.dirname(chemin)
    if dossier:
        os.makedirs(dossier, exist_ok=True)

    if sys.platform == "win32":
        open(chemin, "w", encoding="utf-8").close()
        restreint = _restreindre_acces_windows(chemin)
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(conf, f, ensure_ascii=False, indent=2)
        if restreint:
            print(f"[sécurité] Identifiants écrits en clair dans {chemin} (accès restreint à l'utilisateur courant).")
        else:
            print(f"[sécurité] Identifiants écrits en clair dans {chemin} — accès NON restreint, voir l'avertissement ci-dessus.")
        return

    permissions_prealables_trop_larges = (
        os.path.exists(chemin)
        and stat.S_IMODE(os.stat(chemin).st_mode) != 0o600
    )

    descripteur = os.open(chemin, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descripteur, "w", encoding="utf-8") as f:
            json.dump(conf, f, ensure_ascii=False, indent=2)
    finally:
        pass

    if permissions_prealables_trop_larges:
        os.chmod(chemin, 0o600)

    print(f"[sécurité] Identifiants écrits en clair dans {chemin} (permissions 0600).")


_ACL_WINDOWS_LARGES = ("Everyone", "Tout le monde", "BUILTIN\\Users", "BUILTIN\\Utilisateurs")


def verifier_permissions_conf(chemin: str) -> None:
    """À la lecture d'un fichier de conf existant : avertit si ses permissions sont plus
    larges que ``0600``. Ne modifie rien. Ne fait rien si le fichier n'existe pas.

    Sous Windows : ``os.stat().st_mode`` ne reflète jamais une restriction d'accès par
    compte (NTFS, pas de permissions POSIX), donc inutilisable ici — repose plutôt sur
    une interrogation ``icacls`` best-effort (avertit seulement sur des motifs connus
    pour être trop larges ; silencieux si ``icacls`` échoue, par cohérence avec
    :func:`_restreindre_acces_windows` qui n'échoue jamais). Sans ce filet, une
    restriction qui aurait silencieusement échoué à l'écriture (voir
    :func:`_restreindre_acces_windows`) ne serait jamais re-signalée — contrairement au
    chemin POSIX, qui avertit à chaque lecture tant que le problème persiste."""
    if not os.path.exists(chemin):
        return
    if sys.platform == "win32":
        try:
            resultat = subprocess.run(["icacls", chemin], capture_output=True, text=True, check=False)
        except OSError:
            return
        if resultat.returncode == 0 and any(large in resultat.stdout for large in _ACL_WINDOWS_LARGES):
            print(
                f"[sécurité] Attention : {chemin} contient des identifiants en clair avec "
                f"des permissions NTFS potentiellement trop larges ({resultat.stdout.strip()})."
            )
        return
    mode = stat.S_IMODE(os.stat(chemin).st_mode)
    if mode != 0o600:
        print(
            f"[sécurité] Attention : {chemin} contient des identifiants en clair avec "
            f"des permissions {oct(mode)} (plus larges que 0600 attendu)."
        )


_BACKENDS_EN_CLAIR_CONNUS = ("keyrings.alt.file.PlaintextKeyring",)


def _nom_qualifie(obj: object) -> str:
    classe = type(obj)
    return f"{classe.__module__}.{classe.__qualname__}"


def backend_trousseau_est_sain() -> tuple[bool, str]:
    """Résout ``keyring.get_keyring()`` et indique s'il s'agit d'un backend connu pour
    stocker en clair. Ne lève jamais — c'est à l'appelant de décider quoi faire."""
    backend = keyring.get_keyring()
    nom = _nom_qualifie(backend)
    return (nom not in _BACKENDS_EN_CLAIR_CONNUS, nom)


class TrousseauEnClairError(RuntimeError):
    """Le backend de trousseau résolu est connu pour stocker en clair."""


_PREFIXE_SERVICE = "rudi-commune-starterkit"


def _cle_trousseau(url_noeud: str, usr: str) -> str:
    """Clé de service unique par (nœud, utilisateur) — jamais une constante globale."""
    return f"{_PREFIXE_SERVICE}:{url_noeud}:{usr}"


def enregistrer_mot_de_passe_trousseau(url_noeud: str, usr: str, mot_de_passe: str) -> None:
    sain, nom_backend = backend_trousseau_est_sain()
    if not sain:
        raise TrousseauEnClairError(
            f"Backend de trousseau {nom_backend!r} connu pour stocker en clair — "
            "refus d'y enregistrer un mot de passe."
        )
    keyring.set_password(_cle_trousseau(url_noeud, usr), usr, mot_de_passe)


def lire_mot_de_passe_trousseau(url_noeud: str, usr: str) -> str | None:
    sain, nom_backend = backend_trousseau_est_sain()
    if not sain:
        raise TrousseauEnClairError(
            f"Backend de trousseau {nom_backend!r} connu pour stocker en clair — "
            "refus d'y lire un mot de passe."
        )
    return keyring.get_password(_cle_trousseau(url_noeud, usr), usr)


__all__ = [
    "AbsenceTerminalError",
    "TrousseauEnClairError",
    "UrlNoeudNonSecurisee",
    "backend_trousseau_est_sain",
    "ecrire_conf_fichier",
    "email_suspect",
    "email_valide",
    "enregistrer_mot_de_passe_trousseau",
    "lire_mot_de_passe",
    "lire_mot_de_passe_trousseau",
    "valider_url_noeud",
    "verifier_permissions_conf",
]
