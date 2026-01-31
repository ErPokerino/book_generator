"""Router per funzionalita GDPR - Esercizio diritti dell'interessato."""
import os
import sys
import json
import zipfile
from io import BytesIO
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import bcrypt

from app.models import User
from app.agent.user_store import get_user_store
from app.agent.session_store import get_session_store
from app.agent.notification_store import get_notification_store
from app.agent.connection_store import get_connection_store
from app.agent.book_share_store import get_book_share_store
from app.agent.referral_store import get_referral_store
from app.middleware.auth import get_current_user, delete_session
from app.services.storage_service import get_storage_service


router = APIRouter(prefix="/api/gdpr", tags=["gdpr"])


class DeleteAccountRequest(BaseModel):
    """Richiesta cancellazione account."""
    password: str = Field(..., min_length=1, description="Password per conferma cancellazione")
    confirm: bool = Field(False, description="Conferma esplicita della cancellazione")


class ExportDataResponse(BaseModel):
    """Risposta export dati."""
    success: bool
    message: str


@router.get("/export")
async def export_user_data(current_user: User = Depends(get_current_user)):
    """
    Esporta tutti i dati personali dell'utente in formato JSON (Art. 20 GDPR - Portabilita).
    
    Restituisce un file ZIP contenente:
    - profile.json: Dati del profilo utente
    - books.json: Libri creati dall'utente
    - connections.json: Connessioni con altri utenti
    - notifications.json: Notifiche ricevute
    - referrals.json: Inviti inviati
    - shares.json: Condivisioni libri (inviate e ricevute)
    """
    try:
        print(f"[GDPR] Export dati richiesto per utente: {current_user.email}", file=sys.stderr)
        
        # Raccogli tutti i dati
        user_store = get_user_store()
        session_store = get_session_store()
        notification_store = get_notification_store()
        connection_store = get_connection_store()
        book_share_store = get_book_share_store()
        referral_store = get_referral_store()
        
        # Assicura connessione stores
        await user_store.connect()
        await session_store.connect()
        await notification_store.connect()
        await connection_store.connect()
        await book_share_store.connect()
        await referral_store.connect()
        
        # 1. Profilo utente (senza password hash)
        profile_data = {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "role": current_user.role,
            "is_active": current_user.is_active,
            "is_verified": current_user.is_verified,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
            "updated_at": current_user.updated_at.isoformat() if current_user.updated_at else None,
            "privacy_accepted_at": current_user.privacy_accepted_at.isoformat() if current_user.privacy_accepted_at else None,
            "terms_accepted_at": current_user.terms_accepted_at.isoformat() if current_user.terms_accepted_at else None,
            "credits_reset_at": current_user.credits_reset_at.isoformat() if current_user.credits_reset_at else None,
            "mode_credits": current_user.mode_credits.model_dump() if current_user.mode_credits else None,
        }
        
        # 2. Libri dell'utente
        user_sessions = await session_store.get_sessions_by_user(current_user.id)
        books_data = []
        for session in user_sessions:
            book_entry = {
                "id": session.session_id,
                "title": session.draft_title,
                "form_data": session.form_data.model_dump() if session.form_data else None,
                "current_draft": session.current_draft,
                "current_outline": session.current_outline,
                "status": session.status,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                "writing_start_time": session.writing_start_time.isoformat() if session.writing_start_time else None,
                "writing_end_time": session.writing_end_time.isoformat() if session.writing_end_time else None,
                "chapters_count": len(session.book_chapters) if session.book_chapters else 0,
                "critique_score": session.literary_critique.score if session.literary_critique else None,
            }
            books_data.append(book_entry)
        
        # 3. Connessioni
        user_connections = await connection_store.get_user_connections(current_user.id)
        connections_data = []
        for conn in user_connections:
            connections_data.append({
                "id": conn.id,
                "from_user_id": conn.from_user_id,
                "to_user_id": conn.to_user_id,
                "from_user_name": conn.from_user_name,
                "to_user_name": conn.to_user_name,
                "status": conn.status,
                "created_at": conn.created_at.isoformat() if conn.created_at else None,
            })
        
        # 4. Notifiche
        user_notifications = await notification_store.get_user_notifications(current_user.id, limit=1000)
        notifications_data = []
        for notif in user_notifications:
            notifications_data.append({
                "id": notif.id,
                "type": notif.type,
                "title": notif.title,
                "message": notif.message,
                "is_read": notif.is_read,
                "created_at": notif.created_at.isoformat() if notif.created_at else None,
            })
        
        # 5. Referral inviati
        user_referrals = await referral_store.get_user_referrals(current_user.id)
        referrals_data = []
        for ref in user_referrals:
            referrals_data.append({
                "id": ref.id,
                "invited_email": ref.invited_email,
                "status": ref.status,
                "created_at": ref.created_at.isoformat() if ref.created_at else None,
                "registered_at": ref.registered_at.isoformat() if ref.registered_at else None,
            })
        
        # 6. Book shares (inviate e ricevute)
        sent_shares = await book_share_store.get_sent_shares(current_user.id)
        received_shares = await book_share_store.get_received_shares(current_user.id)
        shares_data = {
            "sent": [
                {
                    "id": share.id,
                    "book_session_id": share.book_session_id,
                    "book_title": share.book_title,
                    "recipient_id": share.recipient_id,
                    "recipient_name": share.recipient_name,
                    "status": share.status,
                    "created_at": share.created_at.isoformat() if share.created_at else None,
                }
                for share in sent_shares
            ],
            "received": [
                {
                    "id": share.id,
                    "book_session_id": share.book_session_id,
                    "book_title": share.book_title,
                    "owner_id": share.owner_id,
                    "owner_name": share.owner_name,
                    "status": share.status,
                    "created_at": share.created_at.isoformat() if share.created_at else None,
                }
                for share in received_shares
            ]
        }
        
        # Crea ZIP con tutti i file JSON
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Aggiungi ogni file JSON
            zip_file.writestr('profile.json', json.dumps(profile_data, indent=2, ensure_ascii=False))
            zip_file.writestr('books.json', json.dumps(books_data, indent=2, ensure_ascii=False))
            zip_file.writestr('connections.json', json.dumps(connections_data, indent=2, ensure_ascii=False))
            zip_file.writestr('notifications.json', json.dumps(notifications_data, indent=2, ensure_ascii=False))
            zip_file.writestr('referrals.json', json.dumps(referrals_data, indent=2, ensure_ascii=False))
            zip_file.writestr('shares.json', json.dumps(shares_data, indent=2, ensure_ascii=False))
            
            # Aggiungi file README
            readme_content = f"""EXPORT DATI PERSONALI - NARRAI
==============================

Data export: {datetime.utcnow().isoformat()}
Utente: {current_user.email}

Questo archivio contiene tutti i tuoi dati personali ai sensi dell'Art. 20 GDPR (Diritto alla portabilita).

Contenuto:
- profile.json: I tuoi dati di profilo
- books.json: I libri che hai creato ({len(books_data)} libri)
- connections.json: Le tue connessioni con altri utenti ({len(connections_data)} connessioni)
- notifications.json: Le notifiche ricevute ({len(notifications_data)} notifiche)
- referrals.json: Gli inviti che hai inviato ({len(referrals_data)} inviti)
- shares.json: Le condivisioni di libri (inviate: {len(shares_data['sent'])}, ricevute: {len(shares_data['received'])})

Per domande: privacy@narrai.it
"""
            zip_file.writestr('README.txt', readme_content)
        
        zip_buffer.seek(0)
        
        # Genera nome file con timestamp
        filename = f"narrai_export_{current_user.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"
        
        print(f"[GDPR] Export completato per utente: {current_user.email}", file=sys.stderr)
        
        # Audit log export
        try:
            from app.services.audit_service import get_audit_service
            audit_service = get_audit_service()
            await audit_service.log_data_export(
                user_id=current_user.id,
                user_email=current_user.email
            )
        except Exception as audit_error:
            print(f"[GDPR] Warning: audit log failed: {audit_error}", file=sys.stderr)
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
        
    except Exception as e:
        print(f"[GDPR ERROR] Errore export dati: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore durante l'export dei dati"
        )


@router.delete("/account")
async def delete_account(
    request: DeleteAccountRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Cancella l'account utente e tutti i dati associati (Art. 17 GDPR - Diritto all'oblio).
    
    Questa operazione:
    - Verifica la password per conferma
    - Elimina: account, libri, PDF, copertine
    - Anonimizza: connessioni, condivisioni (mantiene struttura dati)
    - Invalida la sessione corrente
    """
    try:
        print(f"[GDPR] Richiesta cancellazione account per utente: {current_user.email}", file=sys.stderr)
        
        # Verifica conferma esplicita
        if not request.confirm:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Devi confermare esplicitamente la cancellazione dell'account"
            )
        
        # Verifica password
        password_bytes = request.password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        hashed_bytes = current_user.password_hash.encode('utf-8')
        
        if not bcrypt.checkpw(password_bytes, hashed_bytes):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Password non corretta"
            )
        
        # Ottieni tutti gli store necessari
        user_store = get_user_store()
        session_store = get_session_store()
        notification_store = get_notification_store()
        connection_store = get_connection_store()
        book_share_store = get_book_share_store()
        referral_store = get_referral_store()
        storage_service = get_storage_service()
        
        # Assicura connessione stores
        await user_store.connect()
        await session_store.connect()
        await notification_store.connect()
        await connection_store.connect()
        await book_share_store.connect()
        await referral_store.connect()
        
        user_id = current_user.id
        user_email = current_user.email
        
        # 1. Elimina libri dell'utente e file associati
        user_sessions = await session_store.get_sessions_by_user(user_id)
        deleted_books = 0
        for session in user_sessions:
            try:
                # Elimina PDF
                if session.pdf_path:
                    await storage_service.delete_file(session.pdf_path)
                
                # Elimina copertina
                if session.cover_image_path:
                    await storage_service.delete_file(session.cover_image_path)
                
                # Elimina condivisioni associate al libro
                await book_share_store.delete_shares_for_book(session.session_id)
                
                # Elimina sessione
                await session_store.delete(session.session_id)
                deleted_books += 1
            except Exception as book_error:
                print(f"[GDPR] Errore eliminazione libro {session.session_id}: {book_error}", file=sys.stderr)
        
        print(f"[GDPR] Eliminati {deleted_books} libri per utente {user_email}", file=sys.stderr)
        
        # 2. Elimina notifiche
        deleted_notifications = await notification_store.delete_user_notifications(user_id)
        print(f"[GDPR] Eliminate {deleted_notifications} notifiche per utente {user_email}", file=sys.stderr)
        
        # 3. Anonimizza connessioni (mantiene struttura ma rimuove riferimenti)
        await connection_store.anonymize_user_connections(user_id)
        print(f"[GDPR] Connessioni anonimizzate per utente {user_email}", file=sys.stderr)
        
        # 4. Elimina referral inviati
        await referral_store.delete_user_referrals(user_id)
        print(f"[GDPR] Referral eliminati per utente {user_email}", file=sys.stderr)
        
        # 5. Anonimizza condivisioni ricevute
        await book_share_store.anonymize_user_shares(user_id)
        print(f"[GDPR] Condivisioni anonimizzate per utente {user_email}", file=sys.stderr)
        
        # 6. Elimina account utente
        await user_store.delete_user(user_id)
        print(f"[GDPR] Account eliminato per utente {user_email}", file=sys.stderr)
        
        # Audit log cancellazione account
        try:
            from app.services.audit_service import get_audit_service
            audit_service = get_audit_service()
            await audit_service.log_account_deleted(
                user_id=user_id,
                user_email=user_email,
                books_deleted=deleted_books,
                notifications_deleted=deleted_notifications
            )
        except Exception as audit_error:
            print(f"[GDPR] Warning: audit log failed: {audit_error}", file=sys.stderr)
        
        # Log finale
        print(f"[GDPR] Cancellazione account completata per: {user_email}", file=sys.stderr)
        
        return {
            "success": True,
            "message": "Account e tutti i dati associati sono stati eliminati con successo",
            "deleted": {
                "books": deleted_books,
                "notifications": deleted_notifications
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[GDPR ERROR] Errore cancellazione account: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore durante la cancellazione dell'account"
        )


@router.get("/data-summary")
async def get_data_summary(current_user: User = Depends(get_current_user)):
    """
    Restituisce un riepilogo dei dati personali dell'utente.
    Utile per la pagina impostazioni privacy.
    """
    try:
        session_store = get_session_store()
        notification_store = get_notification_store()
        connection_store = get_connection_store()
        
        await session_store.connect()
        await notification_store.connect()
        await connection_store.connect()
        
        # Conta libri
        user_sessions = await session_store.get_sessions_by_user(current_user.id)
        books_count = len(user_sessions)
        
        # Conta notifiche
        notifications_count = await notification_store.count_user_notifications(current_user.id)
        
        # Conta connessioni
        connections = await connection_store.get_user_connections(current_user.id)
        connections_count = len([c for c in connections if c.status == "accepted"])
        
        return {
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "name": current_user.name,
                "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
                "privacy_accepted_at": current_user.privacy_accepted_at.isoformat() if current_user.privacy_accepted_at else None,
                "terms_accepted_at": current_user.terms_accepted_at.isoformat() if current_user.terms_accepted_at else None,
            },
            "data_counts": {
                "books": books_count,
                "notifications": notifications_count,
                "connections": connections_count,
            }
        }
        
    except Exception as e:
        print(f"[GDPR ERROR] Errore data summary: {e}", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nel recupero del riepilogo dati"
        )
