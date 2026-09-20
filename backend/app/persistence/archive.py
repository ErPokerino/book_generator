"""Consistent local backups and legacy-compatible JSON export.

Run from backend: python -m app.persistence.archive backup --output snapshot.sqlite3
"""
import argparse
import json
import os
import sqlite3
from pathlib import Path


def archive_database(source: Path, destination: Path, *, export_json=False):
    source, destination = source.resolve(), destination.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    # Exclusive creation avoids silently replacing an existing archive or the live DB.
    with destination.open("xb"):
        pass
    try:
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as db:
            if export_json:
                db.execute("BEGIN")
                sessions = {}
                for sid, payload in db.execute("SELECT id,payload FROM sessions"):
                    data = json.loads(payload)
                    data["book_chapters"] = [json.loads(row[0]) for row in db.execute(
                        "SELECT payload FROM chapters WHERE session_id=? ORDER BY section_index", (sid,))]
                    sessions[sid] = data
                with destination.open("w", encoding="utf-8") as output:
                    json.dump(sessions, output, ensure_ascii=False, indent=2)
                    output.flush()
                    os.fsync(output.fileno())
            else:
                with sqlite3.connect(destination) as target:
                    db.backup(target)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("format", choices=("backup", "export-json"))
    parser.add_argument("--database", type=Path, default=Path(os.getenv("NARRAI_DB_PATH") or Path(__file__).resolve().parents[2] / "narrai.sqlite3"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    archive_database(args.database, args.output, export_json=args.format == "export-json")
    print(f"Archivio creato: {args.output.resolve()}")


if __name__ == "__main__":
    main()
