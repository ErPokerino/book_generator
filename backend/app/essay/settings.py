from functools import lru_cache
from pathlib import Path
import yaml

@lru_cache
def settings():
    path = Path(__file__).resolve().parents[3] / "config" / "essay.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def stage_model(brief, phase):
    config = settings()
    return brief.model_overrides.get(phase) or brief.llm_model or config["default_model"]
