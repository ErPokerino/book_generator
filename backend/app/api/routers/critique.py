"""Router per gli endpoint delle critiche letterarie."""
import sys
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import Response

from app.models import LiteraryCritique
from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import get_session_async
from app.agent.book_share_store import get_book_share_store
from app.middleware.auth import get_current_user_optional
from app.services.critique_service import (
    generate_critique_audio,
    analyze_pdf_from_bytes,
)

router = APIRouter(prefix="/api/critique", tags=["critique"])


@router.post("/audio/{session_id}")
async def generate_critique_audio_endpoint(
    session_id: str,
    voice_name: Optional[str] = None,
    current_user = Depends(get_current_user_optional),
):
    """
    Genera audio MP3 della critica letteraria usando Google Cloud Text-to-Speech.
    Restituisce un file MP3 che può essere riprodotto nel browser.
    """
    try:
        session_store = get_session_store()
        session = await get_session_async(session_store, session_id, user_id=None)
        
        if not session:
            raise HTTPException(status_code=404, detail=f"Sessione {session_id} non trovata")
        
        # Verifica accesso: ownership o condivisione accettata
        if current_user and session.user_id and session.user_id != current_user.id:
            book_share_store = get_book_share_store()
            await book_share_store.connect()
            has_access = await book_share_store.check_user_has_access(
                book_session_id=session_id,
                user_id=current_user.id,
                owner_id=session.user_id,
            )
            if not has_access:
                raise HTTPException(
                    status_code=403,
                    detail="Accesso negato: questa sessione appartiene a un altro utente o non hai accesso"
                )
        
        audio_content = await generate_critique_audio(session_id, voice_name)
        
        return Response(
            content=audio_content,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f'attachment; filename="critique_{session_id}.mp3"',
                "Cache-Control": "public, max-age=3600",
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CRITIQUE AUDIO] Errore generico: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nella generazione audio: {str(e)}"
        )


@router.post("/analyze-pdf", response_model=LiteraryCritique)
async def analyze_external_pdf(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
):
    """
    Analizza un PDF esterno con l'agente critico letterario.
    I risultati non vengono salvati e servono come benchmark.
    """
    try:
        # Validazione file
        if file.content_type not in ["application/pdf"]:
            if not file.filename or not file.filename.lower().endswith(".pdf"):
                raise HTTPException(
                    status_code=400,
                    detail="Il file deve essere un PDF (application/pdf)"
                )
        
        # Limite dimensione: 50MB
        MAX_FILE_SIZE = 50 * 1024 * 1024
        
        # Leggi il contenuto del file
        pdf_bytes = await file.read()
        
        # Controlla dimensione
        if len(pdf_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File troppo grande. Dimensione massima: {MAX_FILE_SIZE / (1024 * 1024):.0f}MB"
            )
        
        if len(pdf_bytes) == 0:
            raise HTTPException(
                status_code=400,
                detail="Il file PDF è vuoto"
            )
        
        # Usa titolo e autore forniti, altrimenti usa valori di default
        book_title = title or (file.filename and file.filename.replace(".pdf", "") or "Libro")
        book_author = author or "Autore Sconosciuto"
        
        print(f"[EXTERNAL PDF CRITIQUE] Analisi PDF: {file.filename}, Titolo: {book_title}, Autore: {book_author}")
        print(f"[EXTERNAL PDF CRITIQUE] Dimensione PDF: {len(pdf_bytes) / (1024 * 1024):.2f} MB")
        
        # Genera la critica
        try:
            print(f"[EXTERNAL PDF CRITIQUE] Avvio analisi con modello critico...")
            critique_dict = await analyze_pdf_from_bytes(
                pdf_bytes=pdf_bytes,
                title=book_title,
                author=book_author,
            )
            print(f"[EXTERNAL PDF CRITIQUE] Analisi modello completata")
        except Exception as critique_error:
            print(f"[EXTERNAL PDF CRITIQUE] ERRORE durante analisi modello: {critique_error}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Errore durante l'analisi del PDF da parte del modello: {str(critique_error)}"
            )
        
        # Converti il dizionario in LiteraryCritique
        try:
            critique = LiteraryCritique(
                score=critique_dict.get("score", 0.0) if isinstance(critique_dict, dict) else critique_dict.score,
                pros=critique_dict.get("pros", []) if isinstance(critique_dict, dict) else critique_dict.pros,
                cons=critique_dict.get("cons", []) if isinstance(critique_dict, dict) else critique_dict.cons,
                summary=critique_dict.get("summary", "") if isinstance(critique_dict, dict) else critique_dict.summary,
            )
            print(f"[EXTERNAL PDF CRITIQUE] Analisi completata: score={critique.score}")
        except Exception as validation_error:
            print(f"[EXTERNAL PDF CRITIQUE] ERRORE nella validazione risposta: {validation_error}")
            raise HTTPException(
                status_code=500,
                detail=f"Errore nella validazione della risposta del critico: {str(validation_error)}"
            )
        
        return critique
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[EXTERNAL PDF CRITIQUE] Errore nell'analisi: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Errore nell'analisi del PDF: {str(e)}"
        )
