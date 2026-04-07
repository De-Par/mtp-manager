from __future__ import annotations

from .en import CATALOG as EN
from .ru import CATALOG as RU
from .zh import CATALOG as ZH


class Translator:
    def __init__(self, lang: str = "en") -> None:
        self.lang = lang if lang in {"en", "ru", "zh"} else "en"

    def set_lang(self, lang: str) -> None:
        self.lang = lang if lang in {"en", "ru", "zh"} else "en"

    def tr(self, key: str, **kwargs: object) -> str:
        mapping = RU if self.lang == "ru" else ZH if self.lang == "zh" else EN
        template = mapping.get(key, key)
        return template.format(**kwargs) if kwargs else template
