import json
from pathlib import Path

from .config import settings

_LOCALE_DIR = Path(__file__).parent / "locale"


def _load() -> dict[str, dict[str, str]]:
    catalogs: dict[str, dict[str, str]] = {}
    for loc in settings.ALLOWED_LOCALES:
        path = _LOCALE_DIR / f"{loc}.json"
        catalogs[loc] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return catalogs


CATALOGS = _load()


def normalize_locale(raw: str | None) -> str:
    if not raw:
        return settings.DEFAULT_LOCALE
    tag = raw.split(",")[0].split(";")[0].strip().lower().split("-")[0]
    return tag if tag in settings.ALLOWED_LOCALES else settings.DEFAULT_LOCALE


def t(key: str, locale: str | None = None, **params) -> str:
    loc = normalize_locale(locale)
    message = CATALOGS.get(loc, {}).get(key) or CATALOGS.get(settings.DEFAULT_LOCALE, {}).get(key) or key
    return message.format(**params) if params else message
