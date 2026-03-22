"""Helper per ambiente runtime e validazioni startup."""
import os


DEFAULT_SESSION_SECRET = "change-me-in-production-secret-key"
DEFAULT_MONGODB_URI = "mongodb://admin:admin123@localhost:27017/narrai?authSource=admin"


def get_environment() -> str:
    """Restituisce l'ambiente applicativo normalizzato."""
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
    """True se l'app gira in produzione."""
    return get_environment() == "production"


def allow_detailed_diagnostics() -> bool:
    """Abilita diagnostica dettagliata solo fuori produzione o se esplicitamente consentita."""
    if os.getenv("ENABLE_DIAGNOSTIC_DETAILS", "").lower() in {"1", "true", "yes"}:
        return True
    return not is_production()


def get_session_secret() -> str:
    """Legge il secret di sessione, fallendo in produzione se non sicuro."""
    secret = os.getenv("SESSION_SECRET", DEFAULT_SESSION_SECRET)
    if is_production() and secret == DEFAULT_SESSION_SECRET:
        raise RuntimeError("SESSION_SECRET deve essere configurato in produzione.")
    return secret


def get_mongodb_uri() -> str:
    """Legge la Mongo URI, permettendo il fallback locale solo fuori produzione."""
    mongo_uri = os.getenv("MONGODB_URI", DEFAULT_MONGODB_URI)
    if is_production() and mongo_uri == DEFAULT_MONGODB_URI:
        raise RuntimeError("MONGODB_URI deve essere configurata in produzione.")
    return mongo_uri


def is_default_mongodb_uri(uri: str) -> bool:
    """Verifica se la URI è quella di sviluppo locale."""
    return uri == DEFAULT_MONGODB_URI
