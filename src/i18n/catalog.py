from __future__ import annotations

from .en import CATALOG as EN
from .ru import CATALOG as RU


class Translator:
    def __init__(self, lang: str = "en") -> None:
        self.lang = lang if lang in {"en", "ru"} else "en"

    def set_lang(self, lang: str) -> None:
        self.lang = lang if lang in {"en", "ru"} else "en"

    def tr(self, key: str, **kwargs: object) -> str:
        mapping = RU if self.lang == "ru" else EN
        template = mapping.get(key, key)
        return template.format(**kwargs) if kwargs else template
