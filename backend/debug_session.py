"""Debug session is_complete values."""
from app.agent.session_store import get_session_store

store = get_session_store()

print("=== Sessioni con writing_progress ===")
for sid, s in store._sessions.items():
    if s.writing_progress:
        progress = s.writing_progress
        is_complete = progress.get('is_complete', False)
        is_complete_raw = progress.get('is_complete')
        current = progress.get('current_step')
        total = progress.get('total_steps')
        print(f"{sid[:20]}...")
        print(f"  is_complete (raw): {is_complete_raw} (type: {type(is_complete_raw).__name__})")
        print(f"  is_complete (bool): {is_complete}")
        print(f"  current_step: {current}, total_steps: {total}")
        print()


