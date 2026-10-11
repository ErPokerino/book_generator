"""Copy an existing SaggIA archive into NarrAI without changing the source."""
import argparse
import json
from pathlib import Path
import shutil
import sqlite3


def import_archive(source: Path, target: Path):
    source = source.resolve()
    target = target.resolve()
    source_db = source / "saggia.sqlite3"
    target_db = target / "saggia.sqlite3"
    if source == target:
        raise ValueError("L'archivio è già nella destinazione.")
    if target.exists() and any(target.iterdir()):
        raise ValueError("La destinazione contiene già dati: nessun file è stato sostituito.")
    with sqlite3.connect(source_db.as_uri() + "?mode=ro", uri=True) as original:
        identity = original.execute("SELECT value FROM metadata WHERE key='product_id'").fetchone()
        if identity != ("saggia",):
            raise ValueError("La sorgente non è un archivio SaggIA.")
        target.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(target_db) as destination:
            original.backup(destination)
    for directory in ("sources", "covers"):
        if (source / directory).exists():
            shutil.copytree(source / directory, target / directory)

    def relocate(value):
        if isinstance(value, dict):
            return {key: relocate(item) for key, item in value.items()}
        if isinstance(value, list):
            return [relocate(item) for item in value]
        if isinstance(value, str):
            normalized = value.replace("\\", "/")
            prefix = source.as_posix() + "/"
            if normalized.lower().startswith(prefix.lower()):
                return str(target / normalized[len(prefix):])
        return value

    with sqlite3.connect(target_db) as destination:
        interrupted = {row[0] for row in destination.execute("SELECT session_id FROM jobs WHERE status IN ('pending','running')")}
        for sid, payload in destination.execute("SELECT id,payload FROM sessions").fetchall():
            value = relocate(json.loads(payload))
            if sid in interrupted:
                for field, progress in value.items():
                    if field.endswith("_progress") and isinstance(progress, dict) and progress.get("status") in {"pending", "running"}:
                        progress.update(status="paused", error="Progetto importato in NarrAI. Riprendi il processo dallo studio.")
            destination.execute("UPDATE sessions SET payload=? WHERE id=?", (json.dumps(value, ensure_ascii=False), sid))
        destination.execute("UPDATE jobs SET status='failed',owner=NULL,lease_until=NULL,error='Importato in NarrAI: ripresa esplicita richiesta' WHERE status IN ('pending','running')")
        count = destination.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", type=Path, default=Path(__file__).resolve().parents[1] / "backend/data/saggistica")
    arguments = parser.parse_args()
    count = import_archive(arguments.source, arguments.target)
    print(f"Importati {count} saggi in {arguments.target}. Archivio originale conservato.")
