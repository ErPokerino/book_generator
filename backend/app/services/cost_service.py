"""Compatibility access to the authoritative per-request usage ledger."""
from typing import Optional
from app.agent.session_store import SessionData
from app.services.usage_service import usage_summary


def calculate_real_generation_cost(session: SessionData) -> Optional[float]:
    """Return EUR at the recorded exchange rate only for fully quantified projects."""
    report = usage_summary(session, getattr(session, "_usage_events", []))
    return report["converted_cost_eur"] if report["coverage_complete"] else None
