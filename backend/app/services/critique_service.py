"""Service per la generazione di critiche letterarie."""
import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from app.models import LiteraryCritique
from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import get_session_async
from app.agent.literary_critic import generate_literary_critique_from_pdf


async def analyze_pdf_from_bytes(
    pdf_bytes: bytes,
    title: Optional[str] = None,
    author: Optional[str] = None,
) -> tuple[dict, dict]:
    """
    Analizza un PDF esterno e genera una critica letteraria.
    
    Args:
        pdf_bytes: Bytes del file PDF
        title: Titolo del libro (opzionale)
        author: Autore del libro (opzionale)
    
    Returns:
        Tupla (critique_dict, token_usage)
    """
    critique, token_usage = await generate_literary_critique_from_pdf(
        title=title or "Romanzo",
        author=author or "Autore",
        pdf_bytes=pdf_bytes,
        api_key=None,  # Auto-detect da env
    )
    
    return critique, token_usage
