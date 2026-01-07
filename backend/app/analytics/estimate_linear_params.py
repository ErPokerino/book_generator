#!/usr/bin/env python3
"""
Script per stimare i parametri a e b del modello lineare t(i) = a*i + b
dai dati storici delle sessioni e aggiornare config/app.yaml.

Uso:
    cd backend
    uv run python -m app.analytics.estimate_linear_params
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, List
import yaml
import shutil
from datetime import datetime

# Aggiungi il path del backend per importare i moduli
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv

# Carica variabili d'ambiente
load_dotenv()
load_dotenv(backend_dir.parent / ".env")

from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import get_all_sessions_async
from app.main import get_generation_method, estimate_linear_params_from_history
from app.core.config import get_app_config


async def estimate_and_update_params():
    """Stima i parametri a e b per ogni metodo e aggiorna config/app.yaml."""
    print("=" * 80)
    print("STIMA PARAMETRI MODELLO LINEARE")
    print("=" * 80)
    print()
    
    # Carica session store
    session_store = get_session_store()
    
    # Connetti se è MongoSessionStore
    if hasattr(session_store, 'connect'):
        await session_store.connect()
        print("[STIMA] Connesso a MongoDB")
    else:
        print("[STIMA] Usando FileSessionStore")
    
    # Ottieni tutte le sessioni con chapter_timings
    print("[STIMA] Caricamento sessioni storiche...")
    all_sessions_dict = await get_all_sessions_async(session_store)
    all_sessions = list(all_sessions_dict.values())
    
    # Filtra solo sessioni con chapter_timings
    sessions_with_timings = [
        s for s in all_sessions 
        if s.chapter_timings and len(s.chapter_timings) > 0
    ]
    
    print(f"[STIMA] Trovate {len(all_sessions)} sessioni totali")
    print(f"[STIMA] Sessioni con chapter_timings: {len(sessions_with_timings)}")
    print()
    
    # Raggruppa per metodo
    sessions_by_method: Dict[str, List] = {
        'flash': [],
        'pro': [],
        'ultra': []
    }
    
    for session in sessions_with_timings:
        if not session.form_data:
            continue
        method = get_generation_method(session.form_data.llm_model)
        if method in sessions_by_method:
            sessions_by_method[method].append(session)
    
    # Mostra statistiche per metodo
    print("=" * 80)
    print("STATISTICHE DATI PER METODO")
    print("=" * 80)
    for method, sessions in sessions_by_method.items():
        total_points = sum(len(s.chapter_timings) for s in sessions)
        print(f"\n{method.upper()}:")
        print(f"  Sessioni: {len(sessions)}")
        print(f"  Punti dati totali: {total_points}")
        if sessions:
            avg_chapters = total_points / len(sessions)
            print(f"  Media capitoli per sessione: {avg_chapters:.1f}")
    print()
    
    # Leggi configurazione attuale
    config_path = backend_dir.parent / "config" / "app.yaml"
    if not config_path.exists():
        print(f"[ERRORE] File di configurazione non trovato: {config_path}")
        return
    
    # Backup del file di configurazione
    backup_path = config_path.with_suffix('.yaml.backup')
    shutil.copy2(config_path, backup_path)
    print(f"[STIMA] Backup creato: {backup_path}")
    print()
    
    # Leggi YAML
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Stima parametri per ogni metodo
    print("=" * 80)
    print("STIMA PARAMETRI")
    print("=" * 80)
    
    time_estimation = config.get('time_estimation', {})
    linear_params = time_estimation.get('linear_model_params', {})
    
    updated_methods = []
    
    for method in ['flash', 'pro', 'ultra']:
        print(f"\n{method.upper()}:")
        sessions = sessions_by_method[method]
        
        if len(sessions) == 0:
            print(f"  Nessuna sessione disponibile, mantengo valori attuali")
            continue
        
        # Stima parametri
        estimated = estimate_linear_params_from_history(sessions, method)
        
        if estimated is None:
            print(f"  Dati insufficienti per stima (serve almeno 2 punti dati)")
            print(f"  Mantengo valori attuali: a={linear_params.get(method, {}).get('a', 'N/A')}, b={linear_params.get(method, {}).get('b', 'N/A')}")
            continue
        
        a_estimated, b_estimated = estimated
        
        # Valori attuali
        current_params = linear_params.get(method, {})
        a_current = current_params.get('a', None)
        b_current = current_params.get('b', None)
        
        print(f"  Parametri stimati: a={a_estimated:.4f} s/cap, b={b_estimated:.2f} s")
        if a_current is not None and b_current is not None:
            print(f"  Valori attuali:    a={a_current:.4f} s/cap, b={b_current:.2f} s")
            print(f"  Differenza:        a={a_estimated - a_current:+.4f} s/cap, b={b_estimated - b_current:+.2f} s")
        
        # Aggiorna configurazione
        if method not in linear_params:
            linear_params[method] = {}
        
        linear_params[method]['a'] = round(a_estimated, 4)
        linear_params[method]['b'] = round(b_estimated, 2)
        updated_methods.append(method)
    
    # Salva configurazione aggiornata
    if updated_methods:
        print()
        print("=" * 80)
        print("AGGIORNAMENTO CONFIGURAZIONE")
        print("=" * 80)
        
        # Assicurati che la struttura esista
        if 'time_estimation' not in config:
            config['time_estimation'] = {}
        config['time_estimation']['linear_model_params'] = linear_params
        
        # Salva YAML preservando i commenti (usa ruamel.yaml se disponibile, altrimenti yaml standard)
        try:
            import ruamel.yaml
            yaml_ruamel = ruamel.yaml.YAML()
            yaml_ruamel.preserve_quotes = True
            yaml_ruamel.width = 4096
            
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml_ruamel.dump(config, f)
            print(f"[STIMA] Configurazione aggiornata con ruamel.yaml (commenti preservati)")
        except ImportError:
            # Fallback a yaml standard (perde commenti)
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            print(f"[STIMA] Configurazione aggiornata con yaml standard (commenti potrebbero essere persi)")
            print(f"[STIMA] NOTA: Installa ruamel.yaml per preservare i commenti: pip install ruamel.yaml")
        
        print(f"[STIMA] Metodi aggiornati: {', '.join(updated_methods)}")
        print(f"[STIMA] File aggiornato: {config_path}")
        print(f"[STIMA] Backup disponibile: {backup_path}")
    else:
        print()
        print("[STIMA] Nessun metodo aggiornato (dati insufficienti per tutti i metodi)")
        # Ripristina backup se non abbiamo fatto modifiche
        shutil.copy2(backup_path, config_path)
        print(f"[STIMA] Configurazione ripristinata dal backup")
    
    print()
    print("=" * 80)
    print("COMPLETATO")
    print("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(estimate_and_update_params())
    except KeyboardInterrupt:
        print("\n[STIMA] Interrotto dall'utente")
        sys.exit(1)
    except Exception as e:
        print(f"\n[STIMA] ERRORE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
