"""Per-request metering. Provider usage is evidence; a price calculation is not an invoice."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

SOURCE = "https://ai.google.dev/gemini-api/docs/pricing"
VERIFIED_AT = "2026-09-20"
# USD / million tokens, Standard paid tier. Persisted with every request.
RATES = {
    "gemini-3.8-flash": {"input": .75, "output": 3.75, "cached": .075, "storage": .50},
    "gemini-3.5-flash-lite": {"input": .30, "output": 2.50, "cached": .03, "storage": 1.0},
    "gemini-3.1-flash-lite": {"input": .25, "output": 1.50, "cached": .025, "storage": 1.0},
    "gemini-3.1-pro-preview": {"input": 2., "output": 12., "cached": .20, "storage": 4.50},
    "gemini-3-flash-preview": {"input": .50, "output": 3., "cached": .05, "storage": 1.0},
    "gemini-3.1-flash-image": {"input": .50, "output": 3., "image": 60.},
    "gemini-3.1-flash-lite-image": {"input": .25, "output": 1.50, "image": 30.},
    "gemini-3.1-flash-tts-preview": {"input": 1., "output": 20.},
}


def pricing_snapshot(model, input_tokens=0, at=None):
    rates = RATES.get(model)
    if rates is None:
        return None
    rates = rates.copy()
    date = datetime.fromtimestamp(at or time.time(), timezone.utc).date().isoformat()
    if model == "gemini-3.8-flash" and date >= "2027-01-01":
        rates = {key: value * 2 for key, value in rates.items()}
    if model == "gemini-3.1-pro-preview" and input_tokens > 200_000:
        rates.update(input=4., output=18., cached=.40)
    return {"rates": rates, "source": SOURCE, "verified_at": VERIFIED_AT, "tier": "standard_paid", "currency": "USD"}


def _dict(value):
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return vars(value) if hasattr(value, "__dict__") else {}


def normalize_usage(response):
    if isinstance(response, dict) and "raw" in response:
        response = response["raw"]
    usage = _dict(getattr(response, "usage_metadata", None))
    if not usage:
        usage = _dict(getattr(response, "response_metadata", {})).get("token_usage") or {}
    if not usage:
        return None
    native = "prompt_token_count" in usage
    def count(key):
        return max(0, int(usage.get(key) or 0))
    if native:
        if usage.get("prompt_token_count") is None or usage.get("candidates_token_count") is None:
            return None
        thoughts = count("thoughts_token_count")
        details = usage.get("candidates_tokens_details") or []
        image_tokens = sum(int(_dict(d).get("token_count") or 0) for d in details
                           if str(_dict(d).get("modality", "")).upper().endswith("IMAGE"))
        return {"input_tokens": count("prompt_token_count"),
                "output_tokens": count("candidates_token_count") + thoughts,
                "thinking_tokens": thoughts, "cached_tokens": count("cached_content_token_count"),
                "image_tokens": image_tokens, "output_modalities_reported": bool(details)}
    if not any(k in usage for k in ("input_tokens", "prompt_tokens")):
        return None
    if usage.get("input_tokens", usage.get("prompt_tokens")) is None or usage.get("output_tokens", usage.get("completion_tokens")) is None:
        return None
    # LangChain already includes reasoning in output_tokens (do not add twice).
    return {"input_tokens": count("input_tokens") if "input_tokens" in usage else count("prompt_tokens"),
            "output_tokens": count("output_tokens") if "output_tokens" in usage else count("completion_tokens"),
            "thinking_tokens": int((usage.get("output_token_details") or {}).get("reasoning") or 0),
            "cached_tokens": int((usage.get("input_token_details") or {}).get("cache_read") or 0),
            "image_tokens": 0, "output_modalities_reported": False}


def price_usage(usage, pricing):
    if usage is None or pricing is None:
        return None
    rates = pricing["rates"]
    if "image" in rates and not usage.get("output_modalities_reported"):
        return None  # Do not assume all output tokens are images, or charge a made-up flat fee.
    incoming = usage["input_tokens"]
    cached = usage.get("cached_tokens", 0)
    images = usage.get("image_tokens", 0)
    if cached > incoming or images > usage["output_tokens"] or (cached and "cached" not in rates):
        return None
    d = lambda x: Decimal(str(x))
    result = (d(incoming-cached)*d(rates["input"]) + d(cached)*d(rates.get("cached", 0))
              + d(usage["output_tokens"]-images)*d(rates["output"]) + d(images)*d(rates.get("image", 0))) / d(1_000_000)
    return float(result)


def _meter_store(session_id):
    from app.agent import session_store
    store = session_store._session_store
    if session_id and store is not None and hasattr(store, "record_usage") and store.get_session(session_id):
        return store
    return None


async def metered_call(call, *, session_id, model, phase):
    store = _meter_store(session_id)
    event = {"id": str(uuid4()), "session_id": session_id, "model": model, "phase": phase,
             "created_at": time.time(), "status": "started", "usage": None, "cost_usd": None}
    from app.core.config import get_exchange_rate_usd_to_eur
    event["usd_to_eur"] = get_exchange_rate_usd_to_eur()
    if store:
        store.record_usage(event)
    try:
        response = await call()
    except BaseException as exc:
        event.update(status="unknown", error_type=type(exc).__name__)
        if store:
            store.record_usage(event)
        raise
    usage = normalize_usage(response)
    pricing = pricing_snapshot(model, (usage or {}).get("input_tokens", 0), event["created_at"])
    event.update(status="measured" if usage else "unknown", usage=usage, pricing=pricing,
                 cost_usd=price_usage(usage, pricing))
    raw = response.get("raw") if isinstance(response, dict) else response
    event["provider_response_id"] = getattr(raw, "response_id", None) or _dict(getattr(raw, "response_metadata", {})).get("response_id")
    if store:
        store.record_usage(event)
    return response


async def metered_generate_content(function, *, session_id, phase, model, **kwargs):
    return await metered_call(lambda: asyncio.to_thread(function, model=model, **kwargs),
                              session_id=session_id, model=model, phase=phase)


def usage_summary(session, events):
    known = [e for e in events if e.get("cost_usd") is not None]
    unknown = [e for e in events if e.get("cost_usd") is None]
    usd = sum(Decimal(str(e["cost_usd"])) for e in known)
    eur = sum(Decimal(str(e["cost_usd"]))*Decimal(str(e["usd_to_eur"])) for e in known)
    historical = bool(getattr(session, "legacy_cost_unverifiable", False))
    # Older synchronous question requests predated their session/ledger. Their
    # aggregate counters lack the per-call pricing snapshot; don't claim coverage.
    questions = (getattr(session, "token_usage", {}) or {}).get("questions", {})
    if (questions.get("input_tokens", 0) or questions.get("output_tokens", 0)) and not any(
        event.get("phase") == "questions" for event in events
    ):
        historical = True
    phases = {}
    for event in events:
        item = phases.setdefault(event["phase"], {"calls": 0, "cost_usd": 0., "unknown_calls": 0})
        item["calls"] += 1
        item["cost_usd"] += event.get("cost_usd") or 0
        item["unknown_calls"] += event.get("cost_usd") is None
    return {"cost_usd": float(usd) if known else None, "converted_cost_eur": float(eur) if known else None,
            "coverage_complete": not unknown and not historical and bool(events),
            "unquantified_calls": len(unknown), "historical_unverifiable": historical,
            "calls": len(events), "phases": phases, "events": events,
            "pricing_source": SOURCE, "pricing_verified_at": VERIFIED_AT,
            "basis": "standard_paid_list_price", "invoice_verified": False,
            "note": "Costo da consumi API e listino Standard a pagamento. EUR al cambio configurato; tasse, crediti e sconti del tuo account esclusi. La fattura Google resta il riferimento."}
