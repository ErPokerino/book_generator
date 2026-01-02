"""Test rigenerazione copertina tramite endpoint HTTP."""
import requests
import sys
import time

API_BASE = "http://localhost:8000/api"

def test_regenerate(session_id):
    """Test rigenerazione tramite endpoint."""
    print(f"\n{'='*60}")
    print(f"TEST RIGENERAZIONE VIA ENDPOINT")
    print(f"Session ID: {session_id}")
    print(f"{'='*60}\n")
    
    url = f"{API_BASE}/library/cover/regenerate/{session_id}"
    print(f"URL: {url}")
    print("Invio richiesta POST...\n")
    
    try:
        response = requests.post(url, timeout=120)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n[OK] SUCCESSO!")
            print(f"   Cover path: {result.get('cover_path')}")
            return True
        else:
            error_detail = response.json().get('detail', 'Errore sconosciuto')
            print(f"\n[X] ERRORE: {error_detail}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"\n[X] Errore di connessione: {e}")
        print("Assicurati che il server backend sia in esecuzione su localhost:8000")
        return False

if __name__ == "__main__":
    # Test sul libro problematico
    session_id = "22a4cf32-bb67-4e17-99fa-2eaafa36864b"
    
    print("\n" + "="*60)
    print("TEST RIGENERAZIONE COPERTINA CON PLOT SANITIZZATO")
    print("="*60)
    
    success = test_regenerate(session_id)
    
    if success:
        print("\n[OK] Test completato con successo!")
    else:
        print("\n[X] Test fallito - controlla i log del backend")
