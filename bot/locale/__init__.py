# Copyright (c) 2026 tusar404
# Licensed under the MIT License.

import json
import os

default_lang = "en"
supported_langs = ("en", "ru", "my", "es")

_dir = os.path.dirname(__file__)
_catalogs = {}
for _lang in supported_langs:
    with open(os.path.join(_dir, f"{_lang}.json"), encoding="utf-8") as _f:
        _catalogs[_lang] = json.load(_f)

language_names = {code: _catalogs[code]["language_name"] for code in supported_langs}


def normalize_lang(lang: str | None) -> str:
    return lang if lang in supported_langs else default_lang


def text(key: str, lang: str = default_lang, **kwargs) -> str:
    lang = normalize_lang(lang)
    value = _catalogs[lang].get(key)
    if value is None:
        value = _catalogs[default_lang].get(key, key)
    return value.format(**kwargs) if kwargs else value
