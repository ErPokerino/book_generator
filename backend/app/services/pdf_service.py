"""Servizio per la generazione e gestione di file PDF."""
from pathlib import Path
from io import BytesIO
from datetime import datetime
import base64
import markdown
from typing import Optional
from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER
from xhtml2pdf import pisa
from app.agent.session_store import SessionData
from app.core.config import get_app_config
from app.services.storage_service import get_storage_service


def get_model_abbreviation(model_name: str) -> str:
    """
    Converte il nome completo del modello in una versione abbreviata per il nome del PDF.
    
    Args:
        model_name: Nome completo del modello (es: "gemini-2.5-flash", "gemini-3-pro-preview")
    
    Returns:
        Abbreviazione del modello (es: "g25f", "g3p")
    """
    model_lower = model_name.lower()
    if "gemini-2.5-flash" in model_lower:
        return "g25f"
    elif "gemini-2.5-pro" in model_lower:
        return "g25p"
    elif "gemini-3-flash" in model_lower:
        return "g3f"
    elif "gemini-3-pro" in model_lower:
        return "g3p"
    else:
        # Fallback: usa le prime lettere del modello
        return model_name.replace("gemini-", "g").replace("-", "").replace("_", "")[:6]


def escape_html(text: str) -> str:
    """Escapa caratteri speciali per HTML."""
    if not text:
        return ""
    return (text.replace("&", "&amp;")
              .replace("<", "&lt;")
              .replace(">", "&gt;")
              .replace('"', "&quot;")
              .replace("'", "&#39;"))


def markdown_to_html(text: str) -> str:
    """Converte markdown base a HTML."""
    if not text:
        return ""
    # Usa la libreria markdown per conversione completa
    html = markdown.markdown(text, extensions=['nl2br', 'fenced_code'])
    return html


def calculate_page_count(content: str) -> int:
    """Calcola il numero di pagine basato sul contenuto (parole/250 arrotondato per eccesso)."""
    import math
    if not content:
        return 0
    try:
        app_config = get_app_config()
        words_per_page = app_config.get("validation", {}).get("words_per_page", 250)
        
        # Conta le parole dividendo per spazi
        words = content.split()
        word_count = len(words)
        # Calcola pagine: parole/words_per_page arrotondato per eccesso
        page_count = math.ceil(word_count / words_per_page)
        return max(1, page_count)  # Almeno 1 pagina
    except Exception as e:
        print(f"[CALCULATE_PAGE_COUNT] Errore nel calcolo pagine: {e}")
        return 0


def generate_summary_pdf(session: SessionData) -> tuple[bytes, str]:
    """
    Genera un PDF con tutte le informazioni del romanzo (configurazione, bozza, outline).
    
    Args:
        session: SessionData object
        
    Returns:
        Tupla (pdf_bytes, filename)
    """
    # Crea il PDF in memoria
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    # Stile per i titoli
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor='#213547',
        spaceAfter=12,
        alignment=TA_CENTER,
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor='#213547',
        spaceAfter=10,
        spaceBefore=12,
    )
    
    # Titolo del documento
    if session.current_title:
        story.append(Paragraph(session.current_title, title_style))
    else:
        story.append(Paragraph("Romanzo", title_style))
    
    if session.form_data.user_name:
        story.append(Paragraph(f"Autore: {session.form_data.user_name}", styles['Normal']))
    
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("=" * 50, styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Configurazione iniziale
    story.append(Paragraph("Configurazione Iniziale", heading_style))
    
    config_lines = []
    config_lines.append(f"<b>Modello LLM:</b> {session.form_data.llm_model}")
    config_lines.append(f"<b>Trama iniziale:</b> {session.form_data.plot}")
    
    optional_fields = {
        "Genere": session.form_data.genre,
        "Sottogenere": session.form_data.subgenre,
        "Tema": session.form_data.theme,
        "Protagonista": session.form_data.protagonist,
        "Arco del personaggio": session.form_data.character_arc,
        "Punto di vista": session.form_data.point_of_view,
        "Voce narrante": session.form_data.narrative_voice,
        "Stile": session.form_data.style,
        "Struttura temporale": session.form_data.temporal_structure,
        "Ritmo": session.form_data.pace,
        "Realismo": session.form_data.realism,
        "Ambiguità": session.form_data.ambiguity,
        "Intenzionalità": session.form_data.intentionality,
        "Autore di riferimento": session.form_data.author,
    }
    
    for label, value in optional_fields.items():
        if value:
            config_lines.append(f"<b>{label}:</b> {value}")
    
    for line in config_lines:
        story.append(Paragraph(line, styles['Normal']))
        story.append(Spacer(1, 0.1*inch))
    
    # Risposte alle domande
    if session.question_answers:
        story.append(PageBreak())
        story.append(Paragraph("Risposte alle Domande Preliminari", heading_style))
        for qa in session.question_answers:
            if qa.answer:
                story.append(Paragraph(f"<b>Domanda:</b> {qa.question_id}", styles['Normal']))
                story.append(Paragraph(f"<b>Risposta:</b> {qa.answer}", styles['Normal']))
                story.append(Spacer(1, 0.15*inch))
    
    # Bozza estesa validata
    if session.current_draft:
        story.append(PageBreak())
        story.append(Paragraph("Bozza Estesa della Trama", heading_style))
        # Converti markdown base a testo semplice per il PDF
        draft_text = session.current_draft
        # Rimuovi markdown base (##, **, etc.) per semplicità
        draft_text = draft_text.replace("## ", "").replace("### ", "")
        draft_text = draft_text.replace("**", "").replace("*", "")
        # Dividi in paragrafi
        paragraphs = draft_text.split("\n\n")
        for para in paragraphs:
            if para.strip():
                story.append(Paragraph(para.strip(), styles['Normal']))
                story.append(Spacer(1, 0.15*inch))
    
    # Struttura/Indice
    if session.current_outline:
        story.append(PageBreak())
        story.append(Paragraph("Struttura del Romanzo", heading_style))
        # Converti markdown base a testo semplice
        outline_text = session.current_outline
        outline_text = outline_text.replace("## ", "").replace("### ", "")
        outline_text = outline_text.replace("**", "").replace("*", "")
        paragraphs = outline_text.split("\n\n")
        for para in paragraphs:
            if para.strip():
                story.append(Paragraph(para.strip(), styles['Normal']))
                story.append(Spacer(1, 0.15*inch))
    
    # Costruisci il PDF
    doc.build(story)
    buffer.seek(0)
    
    # Nome file
    if session.current_title:
        filename = "".join(c for c in session.current_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = filename.replace(" ", "_")
    else:
        filename = f"Romanzo_{session.session_id[:8]}"
    filename = f"{filename}.pdf"
    
    return buffer.getvalue(), filename


def generate_complete_book_pdf(session: SessionData) -> tuple[bytes, str]:
    """
    Genera un PDF del libro completo con titolo, indice e capitoli usando xhtml2pdf.
    
    Args:
        session: SessionData object
        
    Returns:
        Tupla (pdf_bytes, filename)
    """
    # Leggi il file CSS
    css_path = Path(__file__).parent.parent / "static" / "book_styles.css"
    if not css_path.exists():
        raise Exception(f"File CSS non trovato: {css_path}")
    
    with open(css_path, 'r', encoding='utf-8') as f:
        css_content = f.read()
    
    # Prepara dati libro
    book_title = session.current_title or "Romanzo"
    book_author = session.form_data.user_name or "Autore"
    
    # Prepara immagine copertina
    cover_image_data = None
    cover_image_mime = None
    cover_image_width = None
    cover_image_height = None
    cover_image_style = None
    
    if session.cover_image_path:
        try:
            storage_service = get_storage_service()
            print(f"[BOOK PDF] Caricamento copertina da: {session.cover_image_path}")
            image_bytes = storage_service.download_file(session.cover_image_path)
            print(f"[BOOK PDF] Immagine copertina caricata: {len(image_bytes)} bytes")
            
            # Leggi dimensioni originali dell'immagine con PIL da bytes
            with PILImage.open(BytesIO(image_bytes)) as img:
                cover_image_width, cover_image_height = img.size
            
            # Determina MIME type dal path
            cover_path_str = session.cover_image_path.lower()
            if '.png' in cover_path_str:
                cover_image_mime = 'image/png'
            elif '.jpg' in cover_path_str or '.jpeg' in cover_path_str:
                cover_image_mime = 'image/jpeg'
            else:
                cover_image_mime = 'image/png'  # Default
            
            # Calcola dimensioni per A4 (595.276pt x 841.890pt) mantenendo proporzioni
            a4_width_pt = 595.276
            a4_height_pt = 841.890
            a4_ratio = a4_height_pt / a4_width_pt
            image_ratio = cover_image_height / cover_image_width
            
            # Se l'immagine è più larga che alta rispetto ad A4, usa width: 100%
            # Se l'immagine è più alta che larga rispetto ad A4, usa height: 100%
            if image_ratio > a4_ratio:
                cover_image_style = "width: auto; height: 100%;"
            else:
                cover_image_style = "width: 100%; height: auto;"
            
            # Converti i bytes in base64 per l'HTML
            cover_image_data = base64.b64encode(image_bytes).decode('utf-8')
            print(f"[BOOK PDF] Immagine copertina caricata, MIME: {cover_image_mime}")
            print(f"[BOOK PDF] Base64 generato: {len(cover_image_data)} caratteri")
        except Exception as e:
            print(f"[BOOK PDF] Errore nel caricamento copertina: {e}")
            import traceback
            traceback.print_exc()
    
    # Ordina i capitoli per section_index
    sorted_chapters = sorted(session.book_chapters, key=lambda x: x.get('section_index', 0))
    
    # Prepara HTML per indice
    toc_items = []
    for idx, chapter in enumerate(sorted_chapters, 1):
        chapter_title = chapter.get('title', f'Capitolo {idx}')
        toc_items.append(f'<div class="toc-item">{idx}. {escape_html(chapter_title)}</div>')
    
    toc_html = '\n            '.join(toc_items)
    
    # Prepara HTML per capitoli
    chapters_html = []
    for idx, chapter in enumerate(sorted_chapters, 1):
        chapter_title = chapter.get('title', f'Capitolo {idx}')
        chapter_content = chapter.get('content', '')
        
        # Converti markdown a HTML
        content_html = markdown_to_html(chapter_content)
        
        chapters_html.append(f'''    <div class="chapter">
        <h1 class="chapter-title">{escape_html(chapter_title)}</h1>
        <div class="chapter-content">
            {content_html}
        </div>
    </div>''')
    
    chapters_html_str = '\n\n'.join(chapters_html)
    
    # Genera HTML completo
    cover_section = ''
    image_style = cover_image_style or "width: 100%; height: auto;"
    container_style = "width: 595.276pt; height: 841.890pt; margin: 0; padding: 0; position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center;"
    
    # Usa base64 per la copertina (funziona sia per file locali che GCS)
    if cover_image_data and cover_image_mime:
        cover_section = f'''    <!-- Copertina -->
    <div class="cover-page" style="{container_style}">
        <img src="data:{cover_image_mime};base64,{cover_image_data}" class="cover-image" alt="Copertina" style="{image_style} margin: 0; padding: 0; display: block;">
    </div>
    <div style="page-break-after: always;"></div>'''
        print(f"[BOOK PDF] Copertina aggiunta con base64, stile: {image_style}")
    
    html_content = f'''<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape_html(book_title)}</title>
    <style>
        {css_content}
    </style>
</head>
<body>
    <div class="content-wrapper">
{cover_section}
        
        <!-- Indice -->
        <div class="table-of-contents">
            <h1>Indice</h1>
            <div class="toc-list">
                {toc_html}
            </div>
        </div>
        
        <!-- Capitoli -->
{chapters_html_str}
    </div>
</body>
</html>'''
    
    # Genera PDF con xhtml2pdf
    buffer = BytesIO()
    
    try:
        result = pisa.CreatePDF(
            src=html_content,
            dest=buffer,
            encoding='utf-8'
        )
        
        if result.err:
            raise Exception(f"Errore nella generazione PDF: {result.err}")
    except Exception as e:
        print(f"[BOOK PDF] Errore nella generazione PDF con xhtml2pdf: {e}")
        raise
    
    buffer.seek(0)
    pdf_content = buffer.getvalue()
    
    # Nome file con data, modello e titolo (formato: YYYY-MM-DD_g3p_TitoloLibro.pdf)
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    model_abbrev = get_model_abbreviation(session.form_data.llm_model)
    title_sanitized = "".join(c for c in book_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
    title_sanitized = title_sanitized.replace(" ", "_")
    if not title_sanitized:
        title_sanitized = f"Libro_{session.session_id[:8]}"
    filename = f"{date_prefix}_{model_abbrev}_{title_sanitized}.pdf"
    
    # Salva PDF su GCS o locale tramite StorageService
    try:
        storage_service = get_storage_service()
        user_id = getattr(session, 'user_id', None)  # Ottieni user_id dalla sessione se disponibile
        gcs_path = storage_service.upload_file(
            data=pdf_content,
            destination_path=f"books/{filename}",
            content_type="application/pdf",
            user_id=user_id,
        )
        print(f"[BOOK PDF] PDF salvato: {gcs_path}")
    except Exception as e:
        print(f"[BOOK PDF] Errore nel salvataggio PDF: {e}")
        # Non blocchiamo il download HTTP se il salvataggio fallisce
        gcs_path = None
    
    return pdf_content, filename
