"""Helper per ambiente runtime (locale)."""
import os


def get_environment() -> str:
    """Restituisce l'ambiente applicativo normalizzato. Default: development."""
    raw_value = (
        os.getenv("APP_ENV")
        or os.getenv("ENVIRONMENT")
        or os.getenv("NARRAI_ENV")
        or "development"
    )
    normalized = raw_value.strip().lower()
    aliases = {
        "prod": "production",
        "stage": "staging",
        "dev": "development",
        "local": "development",
    }
    return aliases.get(normalized, normalized)


def is_production() -> bool:
    """True se l'app è marcata come production."""
    return get_environment() == "production"


def allow_detailed_diagnostics() -> bool:
    """Diagnostica dettagliata abilitata in locale, o se ENABLE_DIAGNOSTIC_DETAILS è true."""
    if os.getenv("ENABLE_DIAGNOSTIC_DETAILS", "").lower() in {"1", "true", "yes"}:
        return True
    return not is_production()
