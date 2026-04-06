"""Caricamento centralizzato dei prompt e composizione dei contratti di output."""

from __future__ import annotations

from pathlib import Path


def _iter_candidate_roots(anchor_file: str | None = None) -> list[Path]:
    anchor = Path(anchor_file).resolve() if anchor_file else Path(__file__).resolve()
    candidates: list[Path] = []
    for base in [anchor.parent, *anchor.parents]:
        if base in candidates:
            continue
        candidates.append(base)
    return candidates


def load_prompt_file(
    prompt_filename: str,
    agent_label: str,
    *,
    anchor_file: str | None = None,
) -> str:
    """Carica un prompt dalla directory `config/` risolvendo sia locale sia container."""
    for base_path in _iter_candidate_roots(anchor_file):
        config_path = base_path / "config" / prompt_filename
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as handle:
                return handle.read()
    raise FileNotFoundError(
        f"File prompt per {agent_label} non trovato: config/{prompt_filename}"
    )


def append_contract_instructions(
    base_prompt: str,
    contract_instructions: str,
    *,
    title: str = "CONTRATTO DI OUTPUT OBBLIGATORIO",
) -> str:
    """Accoda istruzioni vincolanti al prompt esistente senza alterare il file sorgente."""
    cleaned_prompt = base_prompt.rstrip()
    cleaned_contract = contract_instructions.strip()
    return f"{cleaned_prompt}\n\n## {title}\n{cleaned_contract}\n"
