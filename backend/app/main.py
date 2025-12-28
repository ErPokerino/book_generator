import os
from pathlib import Path
from typing import Optional
from io import BytesIO
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, PageTemplate, BaseDocTemplate
from reportlab.platypus.frames import Frame
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib import colors
from PIL import Image as PILImage
import markdown
import base64
import math
from xhtml2pdf import pisa
from pathlib import Path as PathLib
from app.config import get_config, reload_config
from app.models import (
    ConfigResponse,
    SubmissionRequest,
    SubmissionResponse,
    QuestionGenerationRequest,
    QuestionsResponse,
    QuestionAnswer,
    AnswersRequest,
    AnswersResponse,
    DraftGenerationRequest,
    DraftResponse,
    DraftModificationRequest,
    DraftValidationRequest,
    DraftValidationResponse,
    OutlineGenerateRequest,
    OutlineResponse,
    BookGenerationRequest,
    BookGenerationResponse,
    BookProgress,
    BookResponse,
    Chapter,
    LiteraryCritique,
)
from app.agent.question_generator import generate_questions
from app.agent.draft_generator import generate_draft
from app.agent.outline_generator import generate_outline
from app.agent.writer_generator import generate_full_book, parse_outline_sections
from app.agent.cover_generator import generate_book_cover
from app.agent.literary_critic import generate_literary_critique_from_pdf
from app.agent.session_store import get_session_store, FileSessionStore

# Carica variabili d'ambiente dal file .env
# Il file .env è nella root del progetto (un livello sopra backend)
# Path(__file__) = backend/app/main.py
# parent = backend/app
# parent.parent = backend
# parent.parent.parent = root del progetto
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Carica anche dalla directory corrente come fallback
load_dotenv()

app = FastAPI(title="Scrittura Libro API", version="0.1.0")

# CORS per sviluppo locale
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/config", response_model=ConfigResponse)
async def get_config_endpoint():
    """Restituisce la configurazione degli input."""
    try:
        # Ricarica sempre la config per permettere modifiche al YAML senza riavviare
        return reload_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore nel caricamento della configurazione: {str(e)}")


@app.post("/api/submissions", response_model=SubmissionResponse)
async def submit_form(data: SubmissionRequest):
    """Riceve e valida i dati del form."""
    try:
        print(f"[SUBMIT FORM] Ricevuta submission con llm_model={data.llm_model}, temperature={data.temperature}")
        config = get_config()
        
        # Valida il modello LLM
        if data.llm_model not in config.llm_models:
            print(f"[SUBMIT FORM] ERRORE: Modello LLM non valido: {data.llm_model}")
            raise HTTPException(
                status_code=400,
                detail=f"Modello LLM non valido: {data.llm_model}. Modelli disponibili: {', '.join(config.llm_models)}"
            )
        
        # Valida la temperatura se presente
        if data.temperature is not None:
            if not (0.0 <= data.temperature <= 1.0):
                print(f"[SUBMIT FORM] ERRORE: Temperatura non valida: {data.temperature}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Temperatura deve essere tra 0.0 e 1.0, ricevuto: {data.temperature}"
                )
        
        # Valida i campi select opzionali contro le opzioni configurate
        # Escludi temperature, llm_model e plot dalla validazione come select
        field_map = {field.id: field for field in config.fields}
        
        for field_id, value in data.model_dump(exclude={"llm_model", "plot", "temperature"}).items():
            if value is not None and field_id in field_map:
                field = field_map[field_id]
                if field.type == "select" and field.options:
                    valid_values = [opt.value for opt in field.options]
                    if value not in valid_values:
                        print(f"[SUBMIT FORM] ERRORE: Valore non valido per '{field.label}': {value}")
                        raise HTTPException(
                            status_code=400,
                            detail=f"Valore non valido per '{field.label}': {value}"
                        )
        
        print(f"[SUBMIT FORM] Submission validata con successo")
        return SubmissionResponse(
            success=True,
            message="Submission ricevuta con successo",
            data=data,
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[SUBMIT FORM] ERRORE CRITICO: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore interno nel processamento della submission: {str(e)}"
        )


@app.post("/api/questions/generate", response_model=QuestionsResponse)
async def generate_questions_endpoint(request: QuestionGenerationRequest):
    """Genera domande preliminari basate sul form compilato."""
    try:
        # Verifica che l'API key sia configurata
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
        # Genera le domande (la funzione userà automaticamente la variabile d'ambiente se non passata)
        response = await generate_questions(request.form_data, api_key=api_key)
        
        # IMPORTANTE: Crea la sessione nel session store subito dopo aver generato le domande
        # Questo garantisce che la sessione esista anche se il backend si riavvia
        session_store = get_session_store()
        try:
            # Crea la sessione con form_data e question_answers vuote (verranno aggiunte dopo)
            session_store.create_session(
                session_id=response.session_id,
                form_data=request.form_data,
                question_answers=[],  # Vuote per ora, verranno aggiunte quando l'utente risponde
            )
            print(f"[DEBUG] Sessione {response.session_id} creata nel session store dopo generazione domande")
        except Exception as session_error:
            # Log l'errore ma non bloccare il flusso
            print(f"[WARNING] Errore nella creazione sessione: {session_error}")
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Errore nella generazione delle domande: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella generazione delle domande: {str(e)}"
        )


@app.post("/api/questions/answers", response_model=AnswersResponse)
async def submit_answers(data: AnswersRequest):
    """Riceve le risposte alle domande e continua il flusso."""
    print(f"[SUBMIT ANSWERS] Ricevute risposte per sessione {data.session_id}")
    print(f"[SUBMIT ANSWERS] Numero di risposte: {len(data.answers)}")
    try:
        # Aggiorna la sessione con le risposte alle domande
        session_store = get_session_store()
        print(f"[SUBMIT ANSWERS] Session store ottenuto: {type(session_store).__name__}")
        
        session = session_store.get_session(data.session_id)
        
        if not session:
            print(f"[SUBMIT ANSWERS] ERRORE: Sessione {data.session_id} NON trovata!")
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {data.session_id} non trovata. Ricarica la pagina e riprova."
            )
        
        print(f"[SUBMIT ANSWERS] Sessione trovata, aggiorno le risposte...")
        # Aggiorna le risposte nella sessione
        session.question_answers = data.answers
        print(f"[SUBMIT ANSWERS] Aggiornate {len(data.answers)} risposte nella sessione")
        
        # Salva la sessione aggiornata
        if isinstance(session_store, FileSessionStore):
            print(f"[SUBMIT ANSWERS] Salvataggio sessioni su file...")
            try:
                session_store._save_sessions()
                print(f"[SUBMIT ANSWERS] Sessioni salvate con successo")
            except Exception as save_error:
                print(f"[SUBMIT ANSWERS] ERRORE nel salvataggio: {save_error}")
                import traceback
                traceback.print_exc()
                # Non blocchiamo il flusso se il salvataggio fallisce, ma logghiamo l'errore
        
        print(f"[SUBMIT ANSWERS] Invio risposta di successo...")
        return AnswersResponse(
            success=True,
            message="Risposte ricevute con successo. Pronto per la fase di scrittura.",
            session_id=data.session_id,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[SUBMIT ANSWERS] ERRORE CRITICO: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nell'elaborazione delle risposte: {str(e)}"
        )


@app.post("/api/draft/generate", response_model=DraftResponse)
async def generate_draft_endpoint(request: DraftGenerationRequest):
    """Genera una bozza estesa della trama."""
    print(f"[DEBUG] Generazione bozza per sessione {request.session_id}")
    try:
        # Verifica che l'API key sia configurata
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("[DEBUG] GOOGLE_API_KEY mancante!")
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
        # Crea o recupera la sessione
        session_store = get_session_store()
        session = session_store.get_session(request.session_id)
        
        if not session:
            print(f"[DEBUG] Sessione {request.session_id} non trovata, creazione nuova...")
            # Crea nuova sessione
            session = session_store.create_session(
                session_id=request.session_id,
                form_data=request.form_data,
                question_answers=request.question_answers,
            )
        
        print("[DEBUG] Chiamata a generate_draft...")
        # Genera la bozza
        draft_text, title, version = await generate_draft(
            form_data=request.form_data,
            question_answers=request.question_answers,
            session_id=request.session_id,
            api_key=api_key,
        )
        
        print(f"[DEBUG] Bozza generata: {title}, v{version}")
        # Salva la bozza nella sessione
        session_store.update_draft(request.session_id, draft_text, version, title=title)
        
        return DraftResponse(
            success=True,
            session_id=request.session_id,
            draft_text=draft_text,
            title=title,
            version=version,
            message="Bozza generata con successo",
        )
    
    except Exception as e:
        print(f"[ERROR] Errore critico in generate_draft_endpoint: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella generazione della bozza: {str(e)}"
        )


@app.post("/api/draft/modify", response_model=DraftResponse)
async def modify_draft_endpoint(request: DraftModificationRequest):
    """Rigenera la bozza con le modifiche richieste dall'utente."""
    try:
        # Verifica che l'API key sia configurata
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
        # Recupera la sessione
        session_store = get_session_store()
        session = session_store.get_session(request.session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {request.session_id} non trovata"
            )
        
        if not session.current_draft:
            raise HTTPException(
                status_code=400,
                detail="Nessuna bozza esistente da modificare"
            )
        
        # Rigenera la bozza con le modifiche
        draft_text, title, version = await generate_draft(
            form_data=session.form_data,
            question_answers=session.question_answers,
            session_id=request.session_id,
            api_key=api_key,
            previous_draft=session.current_draft,
            user_feedback=request.user_feedback,
        )
        
        # Salva la nuova versione
        session_store.update_draft(request.session_id, draft_text, version, title=title)
        
        return DraftResponse(
            success=True,
            session_id=request.session_id,
            draft_text=draft_text,
            title=title,
            version=version,
            message="Bozza modificata con successo",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella modifica della bozza: {str(e)}"
        )


@app.post("/api/draft/validate", response_model=DraftValidationResponse)
async def validate_draft_endpoint(request: DraftValidationRequest):
    """Valida la bozza finale."""
    try:
        session_store = get_session_store()
        session = session_store.get_session(request.session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {request.session_id} non trovata"
            )
        
        if not session.current_draft:
            raise HTTPException(
                status_code=400,
                detail="Nessuna bozza da validare"
            )
        
        if request.validated:
            session_store.validate_session(request.session_id)
            # Log per debug
            print(f"[DEBUG] Bozza validata per sessione {request.session_id}")
            print(f"[DEBUG] Draft presente: {bool(session.current_draft)}")
            print(f"[DEBUG] Titolo: {session.current_title}")
            return DraftValidationResponse(
                success=True,
                session_id=request.session_id,
                message="Bozza validata con successo. Pronto per la fase di scrittura.",
            )
        else:
            return DraftValidationResponse(
                success=False,
                session_id=request.session_id,
                message="Validazione annullata.",
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella validazione della bozza: {str(e)}"
        )


@app.get("/api/draft/{session_id}", response_model=DraftResponse)
async def get_draft_endpoint(session_id: str):
    """Recupera la bozza corrente di una sessione."""
    try:
        session_store = get_session_store()
        session = session_store.get_session(session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        if not session.current_draft:
            raise HTTPException(
                status_code=404,
                detail="Nessuna bozza disponibile per questa sessione"
            )
        
        return DraftResponse(
            success=True,
            session_id=session_id,
            draft_text=session.current_draft,
            title=session.current_title,
            version=session.current_version,
            message="Bozza recuperata con successo",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero della bozza: {str(e)}"
        )


@app.post("/api/outline/generate", response_model=OutlineResponse)
async def generate_outline_endpoint(request: OutlineGenerateRequest):
    """Genera la struttura/indice del libro basandosi sulla bozza validata."""
    try:
        # Verifica che l'API key sia configurata
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
        # Recupera la sessione
        session_store = get_session_store()
        session = session_store.get_session(request.session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {request.session_id} non trovata"
            )
        
        if not session.current_draft:
            raise HTTPException(
                status_code=400,
                detail="Nessuna bozza validata disponibile. Valida prima la bozza estesa."
            )
        
        if not session.validated:
            raise HTTPException(
                status_code=400,
                detail="La bozza deve essere validata prima di generare la struttura."
            )
        
        # Genera l'outline
        print(f"[DEBUG OUTLINE] Inizio generazione outline per sessione {request.session_id}")
        print(f"[DEBUG OUTLINE] Draft length: {len(session.current_draft) if session.current_draft else 0}")
        print(f"[DEBUG OUTLINE] Titolo: {session.current_title}")
        
        outline_text = await generate_outline(
            form_data=session.form_data,
            question_answers=session.question_answers,
            validated_draft=session.current_draft,
            session_id=request.session_id,
            draft_title=session.current_title,
            api_key=api_key,
        )
        
        print(f"[DEBUG OUTLINE] Outline generato, length: {len(outline_text) if outline_text else 0}")
        print(f"[DEBUG OUTLINE] Preview: {outline_text[:200] if outline_text else 'None'}...")
        
        # Salva l'outline nella sessione
        session_store.update_outline(request.session_id, outline_text)
        print(f"[DEBUG OUTLINE] Outline salvato nella sessione")
        
        return OutlineResponse(
            success=True,
            session_id=request.session_id,
            outline_text=outline_text,
            version=session.outline_version,
            message="Struttura generata con successo",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella generazione della struttura: {str(e)}"
        )


@app.get("/api/outline/{session_id}", response_model=OutlineResponse)
async def get_outline_endpoint(session_id: str):
    """Recupera la struttura corrente di una sessione."""
    try:
        session_store = get_session_store()
        session = session_store.get_session(session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        if not session.current_outline:
            raise HTTPException(
                status_code=404,
                detail="Nessuna struttura disponibile per questa sessione"
            )
        
        return OutlineResponse(
            success=True,
            session_id=session_id,
            outline_text=session.current_outline,
            version=session.outline_version,
            message="Struttura recuperata con successo",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero della struttura: {str(e)}"
        )


@app.get("/api/pdf/{session_id}")
async def download_pdf_endpoint(session_id: str):
    """Genera e scarica un PDF con tutte le informazioni del romanzo."""
    try:
        print(f"[DEBUG PDF] Richiesta PDF per sessione: {session_id}")
        session_store = get_session_store()
        session = session_store.get_session(session_id)
        
        if not session:
            print(f"[DEBUG PDF] Sessione {session_id} non trovata")
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        print(f"[DEBUG PDF] Sessione trovata, draft: {bool(session.current_draft)}, outline: {bool(session.current_outline)}")
        
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
            filename = f"Romanzo_{session_id[:8]}"
        filename = f"{filename}.pdf"
        
        return Response(
            content=buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella generazione del PDF: {str(e)}"
        )


class NumberedCanvas:
    """Classe per aggiungere header e footer con numerazione pagine."""
    def __init__(self, canvas, doc, book_title, book_author):
        self.canvas = canvas
        self.doc = doc
        self.book_title = book_title
        self.book_author = book_author
        
    def draw_header_footer(self):
        """Disegna header e footer su ogni pagina."""
        canvas = self.canvas
        page_num = canvas.getPageNumber()
        
        # Salva lo stato corrente
        canvas.saveState()
        
        # Header - linea sottile in alto
        canvas.setStrokeColor(colors.grey)
        canvas.setLineWidth(0.5)
        canvas.line(2*cm, A4[1] - 1.5*cm, A4[0] - 2*cm, A4[1] - 1.5*cm)
        
        # Footer - linea sottile in basso e numero pagina
        canvas.line(2*cm, 1.5*cm, A4[0] - 2*cm, 1.5*cm)
        
        # Numero pagina centrato in basso
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(A4[0] / 2.0, 1*cm, str(page_num))
        
        # Ripristina lo stato
        canvas.restoreState()

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
    if not content:
        return 0
    try:
        # Conta le parole dividendo per spazi
        words = content.split()
        word_count = len(words)
        # Calcola pagine: parole/250 arrotondato per eccesso
        page_count = math.ceil(word_count / 250)
        return max(1, page_count)  # Almeno 1 pagina
    except Exception as e:
        print(f"[CALCULATE_PAGE_COUNT] Errore nel calcolo pagine: {e}")
        return 0

@app.get("/api/book/pdf/{session_id}")
async def download_book_pdf_endpoint(session_id: str):
    """Genera e scarica un PDF del libro completo con titolo, indice e capitoli usando WeasyPrint."""
    try:
        print(f"[BOOK PDF] Richiesta PDF libro completo per sessione: {session_id}")
        session_store = get_session_store()
        session = session_store.get_session(session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        if not session.writing_progress or not session.writing_progress.get('is_complete'):
            raise HTTPException(
                status_code=400,
                detail="Il libro non è ancora completo. Attendi il completamento della scrittura."
            )
        
        if not session.book_chapters or len(session.book_chapters) == 0:
            raise HTTPException(
                status_code=400,
                detail="Nessun capitolo trovato nel libro."
            )
        
        # Prepara dati libro
        book_title = session.current_title or "Romanzo"
        book_author = session.form_data.user_name or "Autore"
        
        print(f"[BOOK PDF] Generazione PDF con WeasyPrint per: {book_title}")
        
        # Leggi il file CSS
        css_path = Path(__file__).parent / "static" / "book_styles.css"
        if not css_path.exists():
            raise Exception(f"File CSS non trovato: {css_path}")
        
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()
        
        print(f"[BOOK PDF] CSS caricato da: {css_path}")
        
        # Prepara immagine copertina
        cover_image_data = None
        cover_image_mime = None
        cover_image_path_for_html = None
        cover_image_width = None
        cover_image_height = None
        cover_image_style = None
        
        print(f"[BOOK PDF] Verifica copertina - cover_image_path nella sessione: {session.cover_image_path}")
        
        if session.cover_image_path and Path(session.cover_image_path).exists():
            try:
                cover_path = Path(session.cover_image_path)
                print(f"[BOOK PDF] Caricamento immagine copertina: {cover_path.absolute()}")
                print(f"[BOOK PDF] File esiste: {cover_path.exists()}")
                print(f"[BOOK PDF] Dimensione file: {cover_path.stat().st_size} bytes")
                
                # Leggi dimensioni originali dell'immagine con PIL
                with PILImage.open(session.cover_image_path) as img:
                    cover_image_width, cover_image_height = img.size
                    print(f"[BOOK PDF] Dimensioni originali immagine: {cover_image_width} x {cover_image_height}")
                    print(f"[BOOK PDF] Proporzioni: {cover_image_width / cover_image_height:.3f}")
                
                # Determina MIME type dal suffisso
                suffix = cover_path.suffix.lower()
                if suffix == '.png':
                    cover_image_mime = 'image/png'
                elif suffix in ['.jpg', '.jpeg']:
                    cover_image_mime = 'image/jpeg'
                else:
                    cover_image_mime = 'image/png'  # Default
                
                # Calcola dimensioni per A4 (595.276pt x 841.890pt) mantenendo proporzioni
                # A4 ratio: 841.890 / 595.276 = 1.414 (circa)
                a4_width_pt = 595.276
                a4_height_pt = 841.890
                a4_ratio = a4_height_pt / a4_width_pt
                image_ratio = cover_image_height / cover_image_width
                
                print(f"[BOOK PDF] Ratio A4: {a4_ratio:.3f}, Ratio immagine: {image_ratio:.3f}")
                
                # Se l'immagine è più larga che alta rispetto ad A4, usa width: 100%
                # Se l'immagine è più alta che larga rispetto ad A4, usa height: 100%
                if image_ratio > a4_ratio:
                    # Immagine più alta: usa height: 100%, width: auto
                    cover_image_style = "width: auto; height: 100%;"
                    print(f"[BOOK PDF] Immagine più alta di A4, uso height: 100%, width: auto")
                else:
                    # Immagine più larga o simile: usa width: 100%, height: auto
                    cover_image_style = "width: 100%; height: auto;"
                    print(f"[BOOK PDF] Immagine più larga di A4, uso width: 100%, height: auto")
                
                # xhtml2pdf potrebbe non supportare base64, quindi usiamo il path del file
                # Convertiamo il path in formato assoluto per xhtml2pdf
                cover_image_path_for_html = str(cover_path.absolute())
                print(f"[BOOK PDF] Path assoluto copertina per HTML: {cover_image_path_for_html}")
                
                # Anche proviamo base64 come fallback
                with open(session.cover_image_path, 'rb') as f:
                    image_bytes = f.read()
                    cover_image_data = base64.b64encode(image_bytes).decode('utf-8')
                print(f"[BOOK PDF] Immagine copertina caricata, MIME: {cover_image_mime}")
                print(f"[BOOK PDF] Base64 generato: {len(cover_image_data)} caratteri")
                print(f"[BOOK PDF] Path file disponibile: {cover_image_path_for_html}")
            except Exception as e:
                print(f"[BOOK PDF] Errore nel caricamento copertina: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"[BOOK PDF] Nessuna copertina disponibile (path: {session.cover_image_path})")
        
        # Ordina i capitoli per section_index
        sorted_chapters = sorted(session.book_chapters, key=lambda x: x.get('section_index', 0))
        
        # Prepara HTML per indice - usa div invece di li per garantire andata a capo
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
        # Usa lo stile calcolato per mantenere le proporzioni
        image_style = cover_image_style or "width: 100%; height: auto;"
        container_style = "width: 595.276pt; height: 841.890pt; margin: 0; padding: 0; position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center;"
        
        # xhtml2pdf su Windows: prova prima con path relativo, poi file://, poi base64
        if cover_image_path_for_html:
            cover_path_obj = Path(cover_image_path_for_html)
            # Prova con path relativo dalla directory di lavoro
            try:
                # Calcola path relativo dalla directory backend
                backend_dir = Path(__file__).parent.parent
                try:
                    rel_path = cover_path_obj.relative_to(backend_dir)
                    cover_src = str(rel_path).replace('\\', '/')
                    print(f"[BOOK PDF] Usando path relativo per copertina: {cover_src}")
                except ValueError:
                    # Se non è possibile path relativo, usa path assoluto con file://
                    # Su Windows, xhtml2pdf potrebbe richiedere formato file:///C:/path
                    abs_path = str(cover_path_obj.absolute()).replace('\\', '/')
                    cover_src = f"file:///{abs_path}"
                    print(f"[BOOK PDF] Usando path assoluto per copertina: {cover_src}")
                
                cover_section = f'''    <!-- Copertina -->
    <div class="cover-page" style="{container_style}">
        <img src="{cover_src}" class="cover-image" alt="Copertina" style="{image_style} margin: 0; padding: 0; display: block;">
    </div>
    <div style="page-break-after: always;"></div>'''
                print(f"[BOOK PDF] Copertina aggiunta con path: {cover_src}, stile: {image_style}")
            except Exception as e:
                print(f"[BOOK PDF] Errore nel setup path copertina: {e}, uso base64")
                if cover_image_data and cover_image_mime:
                    cover_section = f'''    <!-- Copertina -->
    <div class="cover-page" style="{container_style}">
        <img src="data:{cover_image_mime};base64,{cover_image_data}" class="cover-image" alt="Copertina" style="{image_style} margin: 0; padding: 0; display: block;">
    </div>
    <div style="page-break-after: always;"></div>'''
                    print(f"[BOOK PDF] Copertina aggiunta con base64 (fallback dopo errore path), stile: {image_style}")
        elif cover_image_data and cover_image_mime:
            # Fallback a base64 se il path non è disponibile
            cover_section = f'''    <!-- Copertina -->
    <div class="cover-page" style="{container_style}">
        <img src="data:{cover_image_mime};base64,{cover_image_data}" class="cover-image" alt="Copertina" style="{image_style} margin: 0; padding: 0; display: block;">
    </div>
    <div style="page-break-after: always;"></div>'''
            print(f"[BOOK PDF] Copertina aggiunta con base64 (solo base64 disponibile), stile: {image_style}")
        
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
        
        print(f"[BOOK PDF] HTML generato, lunghezza: {len(html_content)} caratteri")
        
        # Genera PDF con xhtml2pdf
        print(f"[BOOK PDF] Generazione PDF con xhtml2pdf...")
        buffer = BytesIO()
        
        try:
            # xhtml2pdf genera PDF direttamente da HTML+CSS
            result = pisa.CreatePDF(
                src=html_content,
                dest=buffer,
                encoding='utf-8'
            )
            
            if result.err:
                raise Exception(f"Errore nella generazione PDF: {result.err}")
            
            print(f"[BOOK PDF] PDF generato con successo")
        except Exception as e:
            print(f"[BOOK PDF] Errore nella generazione PDF con xhtml2pdf: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        buffer.seek(0)
        pdf_content = buffer.getvalue()
        
        # Nome file con data come prefisso (formato: YYYY-MM-DD_TitoloLibro.pdf)
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        title_sanitized = "".join(c for c in book_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        title_sanitized = title_sanitized.replace(" ", "_")
        if not title_sanitized:
            title_sanitized = f"Libro_{session_id[:8]}"
        filename = f"{date_prefix}_{title_sanitized}.pdf"
        
        # Salva PDF su disco nella cartella backend/books/
        try:
            books_dir = Path(__file__).parent.parent / "books"
            books_dir.mkdir(exist_ok=True)
            pdf_path = books_dir / filename
            with open(pdf_path, 'wb') as f:
                f.write(pdf_content)
            print(f"[BOOK PDF] PDF salvato su disco: {pdf_path}")
        except Exception as e:
            print(f"[BOOK PDF] Errore nel salvataggio PDF su disco: {e}")
            import traceback
            traceback.print_exc()
            # Non blocchiamo il download HTTP se il salvataggio fallisce
        
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[BOOK PDF] ERRORE nella generazione del PDF: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella generazione del PDF del libro: {str(e)}"
        )


@app.post("/api/book/critique/{session_id}")
async def regenerate_book_critique_endpoint(session_id: str):
    """
    Rigenera la valutazione critica usando come input il PDF finale del libro.
    Utile per test e per rigenerare in caso di errore.
    """
    session_store = get_session_store()
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Sessione {session_id} non trovata")

    if not session.writing_progress or not session.writing_progress.get("is_complete"):
        raise HTTPException(status_code=400, detail="Il libro non è ancora completo.")

    # Genera/recupera PDF (salvato anche su disco da download_book_pdf_endpoint)
    try:
        session_store.update_critique_status(session_id, "running", error=None)
        pdf_response = await download_book_pdf_endpoint(session_id)
        pdf_bytes = getattr(pdf_response, "body", None) or getattr(pdf_response, "content", None)
        if not isinstance(pdf_bytes, (bytes, bytearray)) or len(pdf_bytes) == 0:
            raise ValueError("PDF bytes non disponibili.")
    except Exception as e:
        session_store.update_critique_status(session_id, "failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Errore nel generare il PDF per la critica: {e}")

    api_key = os.getenv("GOOGLE_API_KEY")
    try:
        critique = await generate_literary_critique_from_pdf(
            title=session.current_title or "Romanzo",
            author=session.form_data.user_name or "Autore",
            pdf_bytes=bytes(pdf_bytes),
            api_key=api_key,
        )
    except Exception as e:
        session_store.update_critique_status(session_id, "failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Errore nella generazione della critica: {e}")

    session_store.update_critique(session_id, critique)
    return critique


@app.get("/health")
async def health():
    """Endpoint di health check."""
    return {"status": "ok"}


@app.get("/api/ping")
async def ping():
    """Endpoint di diagnostica per verificare se il backend è attivo e aggiornato."""
    return {
        "status": "pong",
        "version": "0.1.1",
        "routes": [route.path for route in app.routes]
    }


async def background_book_generation(
    session_id: str,
    form_data: SubmissionRequest,
    question_answers: list[QuestionAnswer],
    validated_draft: str,
    draft_title: Optional[str],
    outline_text: str,
    api_key: str,
):
    """Funzione eseguita in background per generare il libro completo."""
    session_store = get_session_store()
    try:
        print(f"[BOOK GENERATION] Avvio generazione libro per sessione {session_id}")
        
        # Verifica che il progresso sia stato inizializzato
        session = session_store.get_session(session_id)
        if not session or not session.writing_progress:
            print(f"[BOOK GENERATION] WARNING: Progresso non inizializzato per sessione {session_id}, inizializzo ora...")
            # Fallback: inizializza il progresso se non è stato fatto
            sections = parse_outline_sections(outline_text)
            session_store.update_writing_progress(
                session_id=session_id,
                current_step=0,
                total_steps=len(sections),
                current_section_name=sections[0]['title'] if sections else None,
                is_complete=False,
            )
        
        await generate_full_book(
            session_id=session_id,
            form_data=form_data,
            question_answers=question_answers,
            validated_draft=validated_draft,
            draft_title=draft_title,
            outline_text=outline_text,
            api_key=api_key,
        )
        print(f"[BOOK GENERATION] Generazione completata per sessione {session_id}")
        
        # Genera la copertina dopo che il libro è stato completato
        try:
            print(f"[BOOK GENERATION] Avvio generazione copertina per sessione {session_id}")
            session = session_store.get_session(session_id)
            if session:
                cover_path = await generate_book_cover(
                    session_id=session_id,
                    title=draft_title or "Romanzo",
                    author=form_data.user_name or "Autore",
                    plot=validated_draft,
                    api_key=api_key,
                )
                session_store.update_cover_image_path(session_id, cover_path)
                print(f"[BOOK GENERATION] Copertina generata e salvata: {cover_path}")
        except Exception as e:
            print(f"[BOOK GENERATION] ERRORE nella generazione copertina: {e}")
            import traceback
            traceback.print_exc()
            # Non blocchiamo il processo se la copertina fallisce
        
        # Genera la valutazione critica dopo che il libro è stato completato
        try:
            print(f"[BOOK GENERATION] Avvio valutazione critica per sessione {session_id}")
            session = session_store.get_session(session_id)
            if session and session.book_chapters and len(session.book_chapters) > 0:
                # Critica: genera prima il PDF finale (e lo salva su disco), poi passa il PDF al modello multimodale.
                session_store.update_critique_status(session_id, "running", error=None)
                try:
                    pdf_response = await download_book_pdf_endpoint(session_id)
                    pdf_bytes = getattr(pdf_response, "body", None) or getattr(pdf_response, "content", None)
                    if pdf_bytes is None:
                        # Fallback: rigenera via endpoint e prendi il body
                        pdf_bytes = pdf_response.body
                    if not isinstance(pdf_bytes, (bytes, bytearray)) or len(pdf_bytes) == 0:
                        raise ValueError("PDF bytes non disponibili per la critica.")
                except Exception as e:
                    raise RuntimeError(f"Impossibile generare/recuperare PDF per critica: {e}")

                critique = await generate_literary_critique_from_pdf(
                    title=draft_title or "Romanzo",
                    author=form_data.user_name or "Autore",
                    pdf_bytes=bytes(pdf_bytes),
                    api_key=api_key,
                )

                session_store.update_critique(session_id, critique)
                print(f"[BOOK GENERATION] Valutazione critica completata: score={critique.get('score', 0)}")
        except Exception as e:
            print(f"[BOOK GENERATION] ERRORE nella valutazione critica: {e}")
            import traceback
            traceback.print_exc()
            # Niente placeholder: settiamo status failed e salviamo errore per UI (stop polling + retry).
            try:
                session_store.update_critique_status(session_id, "failed", error=str(e))
            except Exception as _e:
                print(f"[BOOK GENERATION] WARNING: impossibile salvare critique_status failed: {_e}")
    except ValueError as e:
        # Errore di validazione (es. outline non valido)
        error_msg = f"Errore di validazione: {str(e)}"
        print(f"[BOOK GENERATION] ERRORE (ValueError): {error_msg}")
        import traceback
        traceback.print_exc()
        # Salva l'errore nel progresso mantenendo il total_steps se già impostato
        session = session_store.get_session(session_id)
        existing_total = 0
        if session and session.writing_progress:
            existing_total = session.writing_progress.get('total_steps', 0)
        
        session_store.update_writing_progress(
            session_id=session_id,
            current_step=0,
            total_steps=existing_total if existing_total > 0 else 1,
            current_section_name=None,
            is_complete=False,
            error=error_msg,
        )
    except Exception as e:
        error_msg = f"Errore nella generazione: {str(e)}"
        print(f"[BOOK GENERATION] ERRORE (Exception): {error_msg}")
        import traceback
        traceback.print_exc()
        # Salva l'errore nel progresso mantenendo il total_steps se già impostato
        session = session_store.get_session(session_id)
        existing_total = 0
        if session and session.writing_progress:
            existing_total = session.writing_progress.get('total_steps', 0)
        
        session_store.update_writing_progress(
            session_id=session_id,
            current_step=0,
            total_steps=existing_total if existing_total > 0 else 1,
            current_section_name=None,
            is_complete=False,
            error=error_msg,
        )


@app.post("/api/book/generate", response_model=BookGenerationResponse)
async def generate_book_endpoint(
    request: BookGenerationRequest,
    background_tasks: BackgroundTasks,
):
    """Avvia la generazione del libro completo in background."""
    try:
        # Verifica che l'API key sia configurata
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY non configurata. Verifica il file .env nella root del progetto."
            )
        
        # Recupera la sessione
        session_store = get_session_store()
        session = session_store.get_session(request.session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {request.session_id} non trovata"
            )
        
        if not session.current_draft or not session.validated:
            raise HTTPException(
                status_code=400,
                detail="La bozza deve essere validata prima di generare il libro."
            )
        
        if not session.current_outline:
            raise HTTPException(
                status_code=400,
                detail="La struttura del libro deve essere generata prima di iniziare la scrittura."
            )
        
        # NUOVO: Parsa l'outline e inizializza il progresso IMMEDIATAMENTE
        try:
            print(f"[BOOK GENERATION] Parsing outline per sessione {request.session_id}...")
            sections = parse_outline_sections(session.current_outline)
            total_sections = len(sections)
            
            if total_sections == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Nessuna sezione trovata nella struttura. Verifica che la struttura sia in formato Markdown corretto."
                )
            
            # Inizializza il progresso PRIMA di avviare il task
            session_store.update_writing_progress(
                session_id=request.session_id,
                current_step=0,
                total_steps=total_sections,
                current_section_name=sections[0]['title'] if sections else None,
                is_complete=False,
            )
            print(f"[BOOK GENERATION] Progresso inizializzato: {total_sections} sezioni da scrivere")
            
        except ValueError as e:
            # Errore nel parsing
            print(f"[BOOK GENERATION] Errore nel parsing outline: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            print(f"[BOOK GENERATION] Errore imprevisto durante l'inizializzazione: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Errore durante l'inizializzazione della scrittura: {str(e)}"
            )
        
        # Avvia la generazione in background
        background_tasks.add_task(
            background_book_generation,
            session_id=request.session_id,
            form_data=session.form_data,
            question_answers=session.question_answers,
            validated_draft=session.current_draft,
            draft_title=session.current_title,
            outline_text=session.current_outline,
            api_key=api_key,
        )
        
        print(f"[BOOK GENERATION] Task di generazione avviato per sessione {request.session_id}")
        
        return BookGenerationResponse(
            success=True,
            session_id=request.session_id,
            message="Generazione del libro avviata. Usa /api/book/progress per monitorare lo stato.",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Errore nell'avvio generazione libro: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nell'avvio della generazione del libro: {str(e)}"
        )


@app.get("/api/book/progress/{session_id}", response_model=BookProgress)
async def get_book_progress_endpoint(session_id: str):
    """Recupera lo stato di avanzamento della scrittura del libro."""
    try:
        session_store = get_session_store()
        session = session_store.get_session(session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        # Costruisci la risposta dal progresso salvato
        progress = session.writing_progress or {}
        chapters = session.book_chapters or []
        
        # Converti i capitoli in oggetti Chapter
        completed_chapters = []
        for ch_dict in chapters:
            content = ch_dict.get('content', '')
            page_count = calculate_page_count(content)
            completed_chapters.append(Chapter(
                title=ch_dict.get('title', ''),
                content=content,
                section_index=ch_dict.get('section_index', 0),
                page_count=page_count,
            ))
        
        # Calcola total_pages se il libro è completato
        total_pages = None
        is_complete = progress.get('is_complete', False)
        if is_complete and len(completed_chapters) > 0:
            # Somma pagine capitoli
            chapters_pages = sum(ch.page_count for ch in completed_chapters)
            # 1 pagina per copertina
            cover_pages = 1
            # Pagine indice: 1 pagina base + 1 ogni 30 capitoli
            toc_pages = math.ceil(len(completed_chapters) / 30)
            total_pages = chapters_pages + cover_pages + toc_pages
        
        # Recupera la valutazione critica se disponibile
        critique = None
        if session.literary_critique:
            try:
                critique = LiteraryCritique(**session.literary_critique)
            except Exception as e:
                print(f"[GET BOOK PROGRESS] Errore nel parsing critique: {e}")

        # Backward-compat: sessioni vecchie potrebbero avere critique senza critique_status
        critique_status = session.critique_status
        critique_error = session.critique_error
        if critique_status is None:
            if critique is not None:
                critique_status = "completed"
            elif is_complete:
                critique_status = "pending"
        
        return BookProgress(
            session_id=session_id,
            current_step=progress.get('current_step', 0),
            total_steps=progress.get('total_steps', 0),
            current_section_name=progress.get('current_section_name'),
            completed_chapters=completed_chapters,
            is_complete=is_complete,
            error=progress.get('error'),
            total_pages=total_pages,
            critique=critique,
            critique_status=critique_status,
            critique_error=critique_error,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero del progresso: {str(e)}"
        )


@app.get("/api/book/{session_id}", response_model=BookResponse)
async def get_complete_book_endpoint(session_id: str):
    """Restituisce il libro completo con tutti i capitoli."""
    try:
        print(f"[GET BOOK] Richiesta libro completo per sessione: {session_id}")
        session_store = get_session_store()
        session = session_store.get_session(session_id)
        
        if not session:
            print(f"[GET BOOK] Sessione {session_id} non trovata")
            raise HTTPException(
                status_code=404,
                detail=f"Sessione {session_id} non trovata"
            )
        
        print(f"[GET BOOK] Sessione trovata. Progresso: {session.writing_progress}, Capitoli: {len(session.book_chapters) if session.book_chapters else 0}")
        
        if not session.writing_progress or not session.writing_progress.get('is_complete'):
            print(f"[GET BOOK] Libro non ancora completo. Progresso: {session.writing_progress}")
            raise HTTPException(
                status_code=400,
                detail="Il libro non è ancora completo. Attendi il completamento della scrittura."
            )
        
        if not session.book_chapters or len(session.book_chapters) == 0:
            print(f"[GET BOOK] Nessun capitolo trovato nella sessione")
            raise HTTPException(
                status_code=400,
                detail="Nessun capitolo trovato nel libro. La scrittura potrebbe non essere stata completata correttamente."
            )
        
        # Converti i capitoli in oggetti Chapter
        chapters = []
        for idx, ch_dict in enumerate(session.book_chapters):
            try:
                content = ch_dict.get('content', '')
                page_count = calculate_page_count(content)
                chapter = Chapter(
                    title=ch_dict.get('title', f'Capitolo {idx + 1}'),
                    content=content,
                    section_index=ch_dict.get('section_index', idx),
                    page_count=page_count,
                )
                chapters.append(chapter)
                print(f"[GET BOOK] Capitolo {idx + 1}: '{chapter.title}' - {len(chapter.content)} caratteri - {page_count} pagine")
            except Exception as e:
                print(f"[GET BOOK] Errore nel processare capitolo {idx}: {e}")
                continue
        
        if len(chapters) == 0:
            raise HTTPException(
                status_code=400,
                detail="Nessun capitolo valido trovato nel libro."
            )
        
        # Ordina per section_index
        chapters.sort(key=lambda x: x.section_index)
        
        # Calcola total_pages
        chapters_pages = sum(ch.page_count for ch in chapters)
        cover_pages = 1  # 1 pagina per copertina
        toc_pages = math.ceil(len(chapters) / 30)  # Pagine indice: 1 pagina base + 1 ogni 30 capitoli
        total_pages = chapters_pages + cover_pages + toc_pages
        
        # Recupera la valutazione critica se disponibile
        critique = None
        if session.literary_critique:
            try:
                critique = LiteraryCritique(**session.literary_critique)
            except Exception as e:
                print(f"[GET BOOK] Errore nel parsing critique: {e}")

        # Backward-compat: sessioni vecchie potrebbero avere critique senza critique_status
        critique_status = session.critique_status
        critique_error = session.critique_error
        if critique_status is None and critique is not None:
            critique_status = "completed"
        
        book_response = BookResponse(
            title=session.current_title or "Romanzo",
            author=session.form_data.user_name or "Autore",
            chapters=chapters,
            total_pages=total_pages,
            critique=critique,
            critique_status=critique_status,
            critique_error=critique_error,
        )
        
        print(f"[GET BOOK] Libro restituito: {book_response.title} di {book_response.author}, {len(chapters)} capitoli, {total_pages} pagine totali")
        return book_response
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[GET BOOK] ERRORE nel recupero del libro completo: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nel recupero del libro completo: {str(e)}"
        )

