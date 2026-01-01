import os
import json
import asyncio
from typing import Any, Optional, Dict

from google import genai
from google.genai import types

from app.core.config import get_literary_critic_config


def _coerce_points_to_list(value: Any) -> list[str]:
    """Normalizza pros/cons a list[str]."""
    if value is None:
        return []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if item is None:
                continue
            s = str(item).strip()
            if s:
                out.append(s)
        return out
    if isinstance(value, str):
        lines = [ln.strip() for ln in value.splitlines()]
        cleaned: list[str] = []
        for ln in lines:
            ln = ln.lstrip("-•* ").strip()
            if ln:
                cleaned.append(ln)
        if not cleaned and value.strip():
            cleaned = [value.strip()]
        return cleaned
    s = str(value).strip()
    return [s] if s else []


def map_critic_model_name(use_fallback: bool = False) -> str:
    """Mappa il nome del modello per il critico letterario."""
    cfg = get_literary_critic_config()
    if use_fallback:
        return cfg.get("fallback_model", "gemini-3-flash-preview")
    return cfg.get("default_model", "gemini-3-pro-preview")


def _response_to_text(response: Any) -> str:
    """Best-effort per ottenere testo da una response google-genai."""
    if response is None:
        return ""
    txt = getattr(response, "text", None)
    if isinstance(txt, str) and txt.strip():
        return txt
    parts = getattr(response, "parts", None)
    if isinstance(parts, list):
        out: list[str] = []
        for p in parts:
            t = getattr(p, "text", None)
            if isinstance(t, str) and t.strip():
                out.append(t)
        return "\n".join(out).strip()
    return str(response)


def parse_critique_response(response_text: str) -> Dict[str, Any]:
    """
    Estrae la valutazione critica dalla risposta del LLM.
    
    Restituisce un dizionario con: score, pros, cons, summary
    """
    # Prova a parsare come JSON
    try:
        # Cerca un blocco JSON nella risposta
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            parsed = json.loads(json_str)
            return {
                "score": float(parsed.get("score", 0)),
                "pros": _coerce_points_to_list(parsed.get("pros", [])),
                "cons": _coerce_points_to_list(parsed.get("cons", [])),
                "summary": str(parsed.get("summary", "") or "")
            }
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[LITERARY_CRITIC] Errore nel parsing JSON: {e}")
    
    # Fallback: parsing manuale
    score = 5.0  # Default
    pros = ""
    cons = ""
    summary = ""
    
    lines = response_text.split('\n')
    current_section = None
    
    for line in lines:
        line_lower = line.lower().strip()
        
        # Cerca score
        if "score" in line_lower or "voto" in line_lower or "valutazione" in line_lower:
            # Cerca un numero tra 0 e 10
            import re
            numbers = re.findall(r'\d+\.?\d*', line)
            if numbers:
                try:
                    score = float(numbers[0])
                    if score > 10:
                        score = 10.0
                    if score < 0:
                        score = 0.0
                except ValueError:
                    pass
        
        # Cerca sezioni
        if "pro" in line_lower or "punti di forza" in line_lower or "pregi" in line_lower:
            current_section = "pros"
            continue
        elif "contro" in line_lower or "punti di debolezza" in line_lower or "difetti" in line_lower:
            current_section = "cons"
            continue
        elif "sintesi" in line_lower or "riassunto" in line_lower or "summary" in line_lower:
            current_section = "summary"
            continue
        
        # Aggiungi contenuto alla sezione corrente
        if current_section == "pros" and line.strip():
            pros += line.strip() + "\n"
        elif current_section == "cons" and line.strip():
            cons += line.strip() + "\n"
        elif current_section == "summary" and line.strip():
            summary += line.strip() + "\n"
    
    # Se non abbiamo trovato nulla, usa tutto come summary
    if not summary and not pros and not cons:
        summary = response_text
    
    return {
        "score": score,
        "pros": _coerce_points_to_list(pros.strip()),
        "cons": _coerce_points_to_list(cons.strip()),
        "summary": summary.strip()
    }


async def generate_literary_critique_from_pdf(
    title: str,
    author: str,
    pdf_bytes: bytes,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Genera una valutazione critica usando come input il PDF finale del libro,
    passato direttamente al modello multimodale (nessuna estrazione/testo, nessun taglio).
    """
    if api_key is None:
        api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY non configurata. Imposta la variabile d'ambiente o passa api_key.")

    cfg = get_literary_critic_config()
    system_prompt = (cfg.get("system_prompt") or "").strip()
    user_prompt = (cfg.get("user_prompt") or "").strip()
    if not system_prompt:
        raise ValueError("Config critico mancante: system_prompt")
    if not user_prompt:
        raise ValueError("Config critico mancante: user_prompt")

    client = genai.Client(api_key=api_key)
    use_fallback = False
    max_retries = int(cfg.get("max_retries", 2))
    temperature = float(cfg.get("temperature", 0.3))
    response_mime_type = cfg.get("response_mime_type")

    pdf_part = types.Part(
        inline_data=types.Blob(
            mime_type="application/pdf",
            data=pdf_bytes,
        )
    )

    for attempt in range(max_retries):
        try:
            model_name = map_critic_model_name(use_fallback)
            print(f"[LITERARY_CRITIC] (PDF multimodale) Tentativo {attempt + 1} con modello {model_name}")

            config_obj = None
            if hasattr(types, "GenerateContentConfig"):
                kwargs: dict[str, Any] = {"temperature": temperature}
                if response_mime_type:
                    kwargs["response_mime_type"] = response_mime_type
                config_obj = types.GenerateContentConfig(**kwargs)

            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part(text=f"{system_prompt}\n\nTitolo: {title}\nAutore: {author}\n\n{user_prompt}"),
                        pdf_part,
                    ],
                )
            ]

            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model_name,
                contents=contents,
                config=config_obj,
            )
            response_text = _response_to_text(response)
            critique = parse_critique_response(response_text)
            return critique

        except Exception as e:
            print(f"[LITERARY_CRITIC] (PDF multimodale) Errore con modello {model_name}: {e}")
            if attempt < max_retries - 1:
                use_fallback = True
                continue
            raise

