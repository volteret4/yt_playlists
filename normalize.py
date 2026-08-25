"""Normalización de texto compartida (parseo de título, matching de ownership).

Misma función que services/lastfm_explorer/normalize.py -- minúsculas + sin
acentos + espacios colapsados, para poder cruzar títulos de YouTube con
nombres de canción/artista en musica_local.sqlite y Airsonic.
"""
import re
import unicodedata


def normalize(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.strip().lower()
    return re.sub(r"\s+", " ", s)
