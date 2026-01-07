#!/usr/bin/env python3
"""
Script per esportare i tempi di generazione per ogni capitolo di ogni libro in CSV.

Include:
- Metodo di generazione (flash, pro, ultra)
- Tempo in secondi per ogni capitolo
- Numero di pagine per ogni capitolo

Uso:
    cd backend
    python -m app.analytics.export_chapter_timings
"""
import asyncio
import os
import sys
import csv
from pathlib import Path
from typing import Dict, List, Optional
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
from app.main import get_generation_method, calculate_page_count


async def export_chapter_timings():
    """Esporta i tempi di generazione per ogni capitolo in CSV."""
    print("=" * 100)
    print("ESPORTAZIONE TEMPI CAPITOLI")
    print("=" * 100)
    print()
    
    # Carica session store
    session_store = get_session_store()
    
    # Connetti se è MongoSessionStore
    if hasattr(session_store, 'connect'):
        await session_store.connect()
        print("[EXPORT] Connesso a MongoDB")
    else:
        print("[EXPORT] Usando FileSessionStore")
    
    # Ottieni tutte le sessioni
    print("[EXPORT] Caricamento sessioni...")
    all_sessions_dict = await get_all_sessions_async(session_store)
    all_sessions = list(all_sessions_dict.values())
    
    # Filtra solo sessioni con chapter_timings e book_chapters
    valid_sessions = []
    for session in all_sessions:
        if not session.form_data:
            continue
        if (session.chapter_timings and len(session.chapter_timings) > 0 and
            session.book_chapters and len(session.book_chapters) > 0):
            valid_sessions.append(session)
    
    print(f"[EXPORT] Trovate {len(all_sessions)} sessioni totali")
    print(f"[EXPORT] Sessioni con dati completi (timings + capitoli): {len(valid_sessions)}")
    print()
    
    if not valid_sessions:
        print("Nessuna sessione con dati completi trovata.")
        return
    
    # Ordina per data di creazione (più recenti prima)
    valid_sessions.sort(key=lambda s: s.created_at if s.created_at else datetime.min, reverse=True)
    
    # Prepara dati per CSV
    csv_rows = []
    
    for session in valid_sessions:
        method = get_generation_method(session.form_data.llm_model if session.form_data else None)
        model_name = session.form_data.llm_model if session.form_data else "N/A"
        title = session.current_title or "N/A"
        session_id_short = session.session_id[:8] + "..."
        created_date = session.created_at.strftime("%Y-%m-%d %H:%M:%S") if session.created_at else "N/A"
        
        # Calcola totali libro
        total_chapters = len(session.chapter_timings)
        total_time_seconds = sum(session.chapter_timings)
        total_time_minutes = total_time_seconds / 60
        
        # Ordina book_chapters per section_index per sicurezza
        sorted_chapters = sorted(session.book_chapters, key=lambda x: x.get('section_index', 0))
        
        # Per ogni capitolo, crea una riga
        # Allinea chapter_timings con book_chapters per indice
        # Assumiamo che chapter_timings[i] corrisponda a book_chapters ordinato per section_index[i]
        num_timings = len(session.chapter_timings)
        num_chapters = len(sorted_chapters)
        
        # Usa il minimo per evitare indici fuori range
        max_index = min(num_timings, num_chapters)
        
        for idx in range(max_index):
            # Estrai dati capitolo
            chapter_dict = sorted_chapters[idx]
            chapter_title = chapter_dict.get('title', f'Capitolo {idx + 1}')
            chapter_content = chapter_dict.get('content', '')
            
            # Estrai tempo (se disponibile)
            timing_seconds = session.chapter_timings[idx] if idx < num_timings else 0.0
            timing_minutes = timing_seconds / 60
            
            # Calcola pagine
            page_count = calculate_page_count(chapter_content)
            
            # Crea riga CSV
            csv_rows.append({
                'session_id': session_id_short,
                'title': title,
                'method': method,
                'model': model_name,
                'created_at': created_date,
                'chapter_number': idx + 1,
                'chapter_title': chapter_title,
                'time_seconds': timing_seconds,
                'time_minutes': timing_minutes,
                'pages': page_count,
                'total_chapters': total_chapters,
                'total_time_seconds': total_time_seconds,
                'total_time_minutes': total_time_minutes
            })
        
        # Se ci sono più timings che capitoli, aggiungi righe per timings extra
        if num_timings > num_chapters:
            for idx in range(num_chapters, num_timings):
                timing_seconds = session.chapter_timings[idx]
                timing_minutes = timing_seconds / 60
                csv_rows.append({
                    'session_id': session_id_short,
                    'title': title,
                    'method': method,
                    'model': model_name,
                    'created_at': created_date,
                    'chapter_number': idx + 1,
                    'chapter_title': f'Capitolo {idx + 1} (contenuto mancante)',
                    'time_seconds': timing_seconds,
                    'time_minutes': timing_minutes,
                    'pages': 0,  # Nessun contenuto
                    'total_chapters': total_chapters,
                    'total_time_seconds': total_time_seconds,
                    'total_time_minutes': total_time_minutes
                })
    
    # Salva CSV
    csv_path = backend_dir.parent / "chapter_timings_export.csv"
    
    # Colonne CSV
    fieldnames = [
        'session_id',
        'title',
        'method',
        'model',
        'created_at',
        'chapter_number',
        'chapter_title',
        'time_seconds',
        'time_minutes',
        'pages',
        'total_chapters',
        'total_time_seconds',
        'total_time_minutes'
    ]
    
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:  # utf-8-sig per BOM (Excel compatibility)
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in csv_rows:
            # Formatta numeri con 2 decimali
            formatted_row = row.copy()
            formatted_row['time_seconds'] = f"{row['time_seconds']:.2f}"
            formatted_row['time_minutes'] = f"{row['time_minutes']:.2f}"
            formatted_row['total_time_seconds'] = f"{row['total_time_seconds']:.2f}"
            formatted_row['total_time_minutes'] = f"{row['total_time_minutes']:.2f}"
            writer.writerow(formatted_row)
    
    print(f"[EXPORT] CSV esportato: {csv_path}")
    print(f"[EXPORT] Totale righe: {len(csv_rows)}")
    print()
    
    # Mostra statistiche per metodo
    print("=" * 100)
    print("STATISTICHE PER METODO")
    print("=" * 100)
    
    stats_by_method = {}
    for row in csv_rows:
        method = row['method']
        if method not in stats_by_method:
            stats_by_method[method] = {
                'sessions': set(),
                'total_chapters': 0,
                'total_time_seconds': 0.0
            }
        stats_by_method[method]['sessions'].add(row['session_id'])
        stats_by_method[method]['total_chapters'] += 1
        stats_by_method[method]['total_time_seconds'] += row['time_seconds']
    
    for method, stats in stats_by_method.items():
        num_sessions = len(stats['sessions'])
        avg_time = stats['total_time_seconds'] / stats['total_chapters'] if stats['total_chapters'] > 0 else 0
        print(f"\n{method.upper()}:")
        print(f"  Sessioni: {num_sessions}")
        print(f"  Totale capitoli: {stats['total_chapters']}")
        print(f"  Tempo totale: {stats['total_time_seconds']:.1f}s ({stats['total_time_seconds']/60:.2f} min)")
        print(f"  Tempo medio per capitolo: {avg_time:.2f}s")
    
    print()
    print("=" * 100)
    print("COMPLETATO")
    print("=" * 100)
    print(f"\nFile esportato: {csv_path}")


if __name__ == "__main__":
    try:
        asyncio.run(export_chapter_timings())
    except KeyboardInterrupt:
        print("\n[EXPORT] Interrotto dall'utente")
        sys.exit(1)
    except Exception as e:
        print(f"\n[EXPORT] ERRORE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
