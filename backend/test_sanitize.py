"""Test della funzione di sanitizzazione plot."""
import sys
from pathlib import Path

backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from app.main import sanitize_plot_for_cover
from app.agent.session_store import get_session_store

def test_sanitize():
    """Test della sanitizzazione."""
    session_id = "22a4cf32-bb67-4e17-99fa-2eaafa36864b"
    session_store = get_session_store()
    session = session_store.get_session(session_id)
    
    if not session:
        print("Sessione non trovata!")
        return
    
    original_plot = session.current_draft or ""
    print(f"Plot originale: {len(original_plot)} caratteri\n")
    print("="*80)
    print("PRIME 500 CARATTERI ORIGINALI:")
    print("="*80)
    print(original_plot[:500])
    print("\n")
    
    sanitized = sanitize_plot_for_cover(original_plot)
    print("="*80)
    print(f"Plot sanitizzato: {len(sanitized)} caratteri")
    print("="*80)
    print(sanitized)
    print("\n")
    
    # Verifica che non contenga contenuti problematici
    problematic = ["fanno l'amore", "post-coito", "scena erotica", "nudità"]
    found = []
    sanitized_lower = sanitized.lower()
    for p in problematic:
        if p in sanitized_lower:
            found.append(p)
    
    if found:
        print(f"[!] ATTENZIONE: Trovate ancora parole problematiche: {found}")
    else:
        print("[OK] Nessuna parola problematica trovata nel plot sanitizzato")

if __name__ == "__main__":
    test_sanitize()
