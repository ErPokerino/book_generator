"""Router per notifiche."""
import sys
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query
from app.models import Notification, NotificationResponse
from app.agent.notification_store import get_notification_store
from app.middleware.auth import get_current_user
from app.models import User


router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=NotificationResponse)
async def get_notifications(
    limit: int = Query(default=50, ge=1, le=100, description="Numero massimo di notifiche da restituire"),
    skip: int = Query(default=0, ge=0, description="Numero di notifiche da saltare (per paginazione)"),
    unread_only: bool = Query(default=False, description="Se True, restituisce solo notifiche non lette"),
    current_user: User = Depends(get_current_user),
):
    """
    Recupera le notifiche dell'utente corrente.
    
    Args:
        limit: Numero massimo di notifiche (1-100, default: 50)
        skip: Numero di notifiche da saltare (default: 0)
        unread_only: Se True, filtra solo non lette
        current_user: Utente corrente (da auth)
    
    Returns:
        NotificationResponse con lista notifiche e conteggio non lette
    """
    notification_store = get_notification_store()
    
    try:
        # Assicurati che il store sia connesso
        await notification_store.connect()
        
        # Recupera notifiche (limit + 1 per verificare se ci sono altre)
        all_notifications = await notification_store.get_notifications(
            user_id=current_user.id,
            limit=limit + 1,  # Uno in più per verificare se ci sono altre
            skip=skip,
            unread_only=unread_only,
        )
        
        # Determina se ci sono altre notifiche e restituisci solo quelle richieste
        has_more = len(all_notifications) > limit
        notifications = all_notifications[:limit]  # Prendi solo le prime 'limit' notifiche
        
        # Recupera conteggio non lette (per badge)
        unread_count = await notification_store.get_unread_count(current_user.id)
        
        # Calcola total (approssimativo per ora - potrebbe essere ottimizzato con count_documents se necessario)
        if unread_only:
            total = unread_count
        else:
            # Per un conteggio preciso, dovremmo fare una query separata con count_documents
            # Per ora usiamo una stima basata su skip + limit + has_more
            total = skip + len(notifications) + (1 if has_more else 0)
        
        return NotificationResponse(
            notifications=notifications,
            unread_count=unread_count,
            total=total,
            has_more=has_more,
        )
    except Exception as e:
        print(f"[NOTIFICATIONS API] ERRORE nel recupero notifiche: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nel recupero delle notifiche: {str(e)}",
        )


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
):
    """
    Recupera solo il conteggio delle notifiche non lette (per badge).
    Endpoint ottimizzato per polling frequente.
    
    Args:
        current_user: Utente corrente (da auth)
    
    Returns:
        Dict con unread_count
    """
    notification_store = get_notification_store()
    
    try:
        await notification_store.connect()
        count = await notification_store.get_unread_count(current_user.id)
        return {"unread_count": count}
    except Exception as e:
        print(f"[NOTIFICATIONS API] ERRORE nel recupero conteggio: {e}", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nel recupero del conteggio: {str(e)}",
        )


@router.patch("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Marca una notifica come letta.
    
    Args:
        notification_id: ID della notifica
        current_user: Utente corrente (da auth)
    
    Returns:
        Dict con success=True se aggiornata
    """
    notification_store = get_notification_store()
    
    try:
        await notification_store.connect()
        success = await notification_store.mark_as_read(notification_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notifica non trovata o già letta",
            )
        
        return {"success": True, "message": "Notifica marcata come letta"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[NOTIFICATIONS API] ERRORE nel marcare notifica come letta: {e}", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nell'aggiornamento della notifica: {str(e)}",
        )


@router.patch("/read-all")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
):
    """
    Marca tutte le notifiche dell'utente come lette.
    
    Args:
        current_user: Utente corrente (da auth)
    
    Returns:
        Dict con success=True e numero di notifiche aggiornate
    """
    notification_store = get_notification_store()
    
    try:
        await notification_store.connect()
        count = await notification_store.mark_all_as_read(current_user.id)
        return {
            "success": True,
            "message": f"{count} notifiche marcate come lette",
            "updated_count": count,
        }
    except Exception as e:
        print(f"[NOTIFICATIONS API] ERRORE nel marcare tutte le notifiche come lette: {e}", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nell'aggiornamento delle notifiche: {str(e)}",
        )


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Elimina una notifica.
    
    Args:
        notification_id: ID della notifica
        current_user: Utente corrente (da auth)
    
    Returns:
        Dict con success=True se eliminata
    """
    notification_store = get_notification_store()
    
    try:
        await notification_store.connect()
        success = await notification_store.delete_notification(notification_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notifica non trovata",
            )
        
        return {"success": True, "message": "Notifica eliminata"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[NOTIFICATIONS API] ERRORE nell'eliminazione notifica: {e}", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nell'eliminazione della notifica: {str(e)}",
        )
