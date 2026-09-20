"""Legacy token counters for progress displays; costs use usage_service's ledger."""


def extract_token_usage(response) -> dict:
    from app.services.usage_service import normalize_usage
    usage = normalize_usage(response) or {}
    return {"input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0)}
