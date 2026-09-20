"""Header HTTP per nomi di file Unicode, senza caratteri di controllo."""
from urllib.parse import quote


def attachment_header(filename: str) -> str:
    return f"attachment; filename*=UTF-8''{quote(filename, safe='')}"
