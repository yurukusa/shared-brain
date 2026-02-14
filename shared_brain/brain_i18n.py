"""
Shared Brain CLI - Internationalization (i18n) engine.

Zero-dependency language detection and message lookup.
Uses simple Python dict catalogs (messages/en.py, messages/ja.py, etc.).
"""

import os
import importlib

_current_lang = None
_messages = {}
_fallback = {}


def detect_language() -> str:
    """Detect language from environment variables.

    Priority: BRAIN_LANG > LC_ALL > LC_MESSAGES > LANG > "en"
    Extracts 2-letter language code from values like "ja_JP.UTF-8".
    """
    for var in ("BRAIN_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var, "")
        if val and val != "C" and val != "POSIX":
            lang = val.split("_")[0].split(".")[0].lower()
            if len(lang) == 2:
                return lang
    return "en"


def init(lang: str = None):
    """Initialize message catalog.

    Falls back to English if the requested language is not available.
    """
    global _current_lang, _messages, _fallback

    if lang is None:
        lang = detect_language()

    # Always load English as fallback
    from shared_brain.messages import en
    _fallback = en.MESSAGES

    if lang == "en":
        _messages = _fallback
    else:
        try:
            mod = importlib.import_module(f"shared_brain.messages.{lang}")
            _messages = mod.MESSAGES
        except (ImportError, AttributeError):
            _messages = _fallback
            lang = "en"

    _current_lang = lang


def msg(key: str, **kwargs) -> str:
    """Get translated message by key.

    Falls back to English, then to the key itself.
    kwargs are used for .format() substitution.
    """
    if not _messages:
        init()

    template = _messages.get(key) or _fallback.get(key) or key

    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template
    return template


def get_lang() -> str:
    """Return current language code."""
    if _current_lang is None:
        init()
    return _current_lang
