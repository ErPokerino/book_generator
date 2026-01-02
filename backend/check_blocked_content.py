"""
Script per verificare il contenuto che causa il blocco della generazione copertina.
"""
import sys
from pathlib import Path

# Aggiungi il path del backend al sys.path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from app.agent.session_store import get_session_store

def check_blocked_book():
    """Verifica il contenuto del libro bloccato."""
    session_id = "22a4cf32-bb67-4e17-99fa-2eaafa36864b"
    
    session_store = get_session_store()
    session = session_store.get_session(session_id)
    
    if not session:
        print(f"ERRORE: Sessione {session_id} non trovata!")
        return
    
    print("="*80)
    print(f"CONTENUTO DEL LIBRO: {session.current_title}")
    print("="*80)
    print(f"\nAutore: {session.form_data.user_name}")
    print(f"Stato: {session.get_status()}")
    print(f"Modello: {session.form_data.llm_model}")
    print(f"Genere: {session.form_data.genre}")
    print(f"Stile copertina: {session.form_data.cover_style}")
    
    print("\n" + "="*80)
    print("TRAMA/PLOT USATA PER GENERARE LA COPERTINA:")
    print("="*80)
    
    plot = session.current_draft or ""
    print(f"\nLunghezza plot: {len(plot)} caratteri")
    print(f"Prime 2000 caratteri:")
    print("-"*80)
    print(plot[:2000])
    print("-"*80)
    
    if len(plot) > 2000:
        print(f"\n... (altri {len(plot) - 2000} caratteri)")
        print(f"\nUltimi 1000 caratteri:")
        print("-"*80)
        print(plot[-1000:])
        print("-"*80)
    
    # Mostra anche il prompt completo che verrebbe generato
    print("\n" + "="*80)
    print("PROMPT COMPLETO CHE VERRÀ INVIATO ALL'API:")
    print("="*80)
    
    title = session.current_title or "Romanzo"
    author = session.form_data.user_name or "Autore"
    
    style_descriptions = {
        "illustrato": "Stile illustrato: usa disegni artistici o pittorici, orientato all'atmosfera. L'immagine deve essere pittorica, evocativa e artistica.",
        "fotografico": "Stile fotografico: usa foto reali o rielaborate per un effetto realistico. L'immagine deve sembrare una fotografia professionale.",
        "tipografico": "Stile tipografico / Minimal: centralità del testo e della composizione grafica. L'immagine deve essere minimale, con focus sulla tipografia e composizione grafica elegante.",
        "simbolico": "Stile simbolico: usa un'immagine o segno metaforico che rappresenta il tema. L'immagine deve essere metaforica e concettuale.",
        "cartoon": "Stile cartoon: illustrazione stilizzata, tono leggero o ironico. L'immagine deve essere un'illustrazione stilizzata, vivace e moderna."
    }
    
    style_instruction = ""
    if session.form_data.cover_style and session.form_data.cover_style in style_descriptions:
        style_instruction = f"\n\n**Stile richiesto:** {style_descriptions[session.form_data.cover_style]}"
    
    prompt = f"""Crea una copertina professionale per un libro con le seguenti informazioni:

**Titolo del libro:** {title}
**Autore:** {author}
**Trama:** {plot}{style_instruction}

La copertina deve includere:
1. Il titolo del libro in modo prominente e leggibile, ben visibile e con un font professionale
2. Il nome dell'autore, posizionato in modo appropriato (tipicamente in basso)
3. Un'immagine visiva che rappresenti la storia, basata sulla trama fornita

La copertina deve essere:
- Professionale e di alta qualità, adatta a un romanzo pubblicato
- Visivamente accattivante e memorabile
- Coerente con il genere e l'atmosfera della storia descritta nella trama
- Con una composizione equilibrata tra testo (titolo e autore) e immagine visiva
- Il testo deve essere chiaramente leggibile e ben integrato con l'immagine di sfondo
- Stile tipografico professionale per titolo e autore"""
    
    print(f"\nLunghezza prompt: {len(prompt)} caratteri")
    print("\n" + "-"*80)
    print(prompt)
    print("-"*80)
    
    # Cerca parole chiave potenzialmente problematiche
    print("\n" + "="*80)
    print("ANALISI PAROLE CHIAVE POTENZIALMENTE PROBLEMATICHE:")
    print("="*80)
    
    problematic_keywords = [
        "violenza", "sangue", "morte", "omicidio", "uccidere", "ucciso",
        "droghe", "drogato", "stupefacenti",
        "sesso", "sessuale", "erotico",
        "terrorismo", "bomba", "esplosione",
        "razzismo", "discriminazione",
        "violenza domestica", "abuso",
    ]
    
    found_keywords = []
    plot_lower = plot.lower()
    for keyword in problematic_keywords:
        if keyword in plot_lower:
            found_keywords.append(keyword)
    
    if found_keywords:
        print(f"\nTrovate {len(found_keywords)} parole chiave potenzialmente problematiche:")
        for keyword in found_keywords:
            # Cerca il contesto attorno alla parola
            idx = plot_lower.find(keyword)
            if idx >= 0:
                start = max(0, idx - 100)
                end = min(len(plot), idx + len(keyword) + 100)
                context = plot[start:end]
                print(f"\n  - '{keyword}' trovata nel contesto:")
                print(f"    ...{context}...")


if __name__ == "__main__":
    check_blocked_book()
