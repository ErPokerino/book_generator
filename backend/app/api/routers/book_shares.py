"""Router per condivisione libri tra utenti."""
import sys
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query
from app.models import (
    BookShare,
    BookShareRequest,
    BookShareResponse,
    BookShareActionRequest,
    User,
    UserResponse,
)
from app.agent.book_share_store import get_book_share_store
from app.agent.connection_store import get_connection_store
from app.agent.notification_store import get_notification_store
from app.agent.user_store import get_user_store
from app.agent.session_store import get_session_store
from app.agent.session_store_helpers import get_session_async, get_all_sessions_async
from app.middleware.auth import get_current_user


router = APIRouter(prefix="/api/books", tags=["book-shares"])


@router.post("/{session_id}/share", response_model=BookShare)
async def share_book(
    session_id: str,
    request: BookShareRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Condividi un libro con un utente.
    
    Args:
        session_id: ID sessione del libro da condividere
        request: Richiesta con email del destinatario
        current_user: Utente corrente (da auth) - deve essere owner del libro
    
    Returns:
        BookShare creata (status: pending)
    """
    book_share_store = get_book_share_store()
    connection_store = get_connection_store()
    notification_store = get_notification_store()
    user_store = get_user_store()
    session_store = get_session_store()
    
    try:
        # Normalizza email
        email = request.recipient_email.lower().strip()
        
        # Verifica che non stia condividendo con se stesso
        if email == current_user.email.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Non puoi condividere un libro con te stesso",
            )
        
        # Recupera sessione libro e verifica ownership
        await session_store.connect()
        session = await get_session_async(session_store, session_id, user_id=current_user.id)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Libro non trovato",
            )
        
        # Verifica ownership
        if session.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Puoi condividere solo i tuoi libri",
            )
        
        # Verifica che il libro sia completato
        if not session.writing_progress or not session.writing_progress.get('is_complete', False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Puoi condividere solo libri completati",
            )
        
        # Cerca utente destinatario
        await user_store.connect()
        target_user = await user_store.get_user_by_email(email)
        
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utente non trovato",
            )
        
        # Verifica che esista connessione ACCEPTED tra utenti
        await connection_store.connect()
        connection = await connection_store.get_connection(current_user.id, target_user.id)
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Devi essere connesso con questo utente prima di condividere un libro",
            )
        
        if connection.status != "accepted":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Devi avere una connessione accettata. Stato attuale: {connection.status}",
            )
        
        # Verifica che non esista già una condivisione
        await book_share_store.connect()
        existing_share = await book_share_store.check_share_exists(
            book_session_id=session_id,
            owner_id=current_user.id,
            recipient_id=target_user.id,
        )
        
        if existing_share:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Libro già condiviso con questo utente",
            )
        
        # Crea condivisione PENDING
        share = await book_share_store.create_book_share(
            book_session_id=session_id,
            owner_id=current_user.id,
            recipient_id=target_user.id,
            status="pending",
        )
        
        # Crea notifica per il destinatario
        await notification_store.connect()
        book_title = session.current_title or "Libro"
        await notification_store.create_notification(
            user_id=target_user.id,
            type="book_shared",
            title="Nuovo libro condiviso",
            message=f"{current_user.name} ha condiviso con te il libro '{book_title}'",
            data={
                "from_user_id": current_user.id,
                "from_user_name": current_user.name,
                "book_session_id": session_id,
                "book_title": book_title,
                "share_id": share.id,
            },
        )
        
        print(f"[BOOK SHARES API] Libro condiviso: {session_id} da {current_user.id} a {target_user.id}", file=sys.stderr)
        
        return share
    except HTTPException:
        raise
    except ValueError as e:
        # Errore da book_share_store (es: condivisione già esistente)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        print(f"[BOOK SHARES API] ERRORE nella condivisione libro: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nella condivisione del libro: {str(e)}",
        )


@router.get("/shares", response_model=BookShareResponse)
async def get_shared_books(
    status: Optional[str] = Query(default=None, description="Filtra per status (pending, accepted, declined)"),
    limit: int = Query(default=50, ge=1, le=100, description="Numero massimo di condivisioni"),
    skip: int = Query(default=0, ge=0, description="Numero di condivisioni da saltare"),
    current_user: User = Depends(get_current_user),
):
    """
    Recupera i libri condivisi con me (come destinatario).
    
    Args:
        status: Filtra per status (opzionale)
        limit: Numero massimo di condivisioni (1-100, default: 50)
        skip: Numero di condivisioni da saltare (default: 0)
        current_user: Utente corrente (da auth)
    
    Returns:
        BookShareResponse con lista condivisioni
    """
    book_share_store = get_book_share_store()
    user_store = get_user_store()
    session_store_instance = get_session_store()
    
    try:
        await book_share_store.connect()
        
        # Recupera condivisioni (limit + 1 per verificare se ci sono altre)
        all_shares = await book_share_store.get_user_shared_books(
            user_id=current_user.id,
            status=status,
            limit=limit + 1,
            skip=skip,
        )
        
        # Determina se ci sono altre condivisioni
        has_more = len(all_shares) > limit
        shares = all_shares[:limit]  # Prendi solo le prime 'limit' condivisioni
        
        # Popola informazioni utente e libro per ogni condivisione
        await user_store.connect()
        await session_store_instance.connect()
        enriched_shares = []
        for share in shares:
            # Recupera info owner
            owner = await user_store.get_user_by_id(share.owner_id)
            
            # Recupera info libro (non richiede ownership per vedere titolo)
            session = await get_session_async(session_store_instance, share.book_session_id, user_id=None)
            
            # Crea condivisione arricchita
            enriched_share = BookShare(
                id=share.id,
                book_session_id=share.book_session_id,
                owner_id=share.owner_id,
                recipient_id=share.recipient_id,
                status=share.status,
                created_at=share.created_at,
                updated_at=share.updated_at,
                owner_name=owner.name if owner else None,
                recipient_name=current_user.name,
                book_title=session.current_title if session else None,
            )
            enriched_shares.append(enriched_share)
        
        # Calcola total (approssimativo)
        total = skip + len(shares) + (1 if has_more else 0)
        
        return BookShareResponse(
            shares=enriched_shares,
            total=total,
            has_more=has_more,
        )
    except Exception as e:
        print(f"[BOOK SHARES API] ERRORE nel recupero libri condivisi: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nel recupero dei libri condivisi: {str(e)}",
        )


@router.get("/shares/sent", response_model=BookShareResponse)
async def get_sent_shares(
    status: Optional[str] = Query(default=None, description="Filtra per status (pending, accepted, declined)"),
    limit: int = Query(default=50, ge=1, le=100, description="Numero massimo di condivisioni"),
    skip: int = Query(default=0, ge=0, description="Numero di condivisioni da saltare"),
    current_user: User = Depends(get_current_user),
):
    """
    Recupera i libri che ho condiviso con altri (come owner).
    
    Args:
        status: Filtra per status (opzionale)
        limit: Numero massimo di condivisioni (1-100, default: 50)
        skip: Numero di condivisioni da saltare (default: 0)
        current_user: Utente corrente (da auth)
    
    Returns:
        BookShareResponse con lista condivisioni
    """
    book_share_store = get_book_share_store()
    user_store = get_user_store()
    session_store_instance = get_session_store()
    
    try:
        await book_share_store.connect()
        
        # Recupera condivisioni (limit + 1 per verificare se ci sono altre)
        all_shares = await book_share_store.get_user_shared_to_others(
            user_id=current_user.id,
            status=status,
            limit=limit + 1,
            skip=skip,
        )
        
        # Determina se ci sono altre condivisioni
        has_more = len(all_shares) > limit
        shares = all_shares[:limit]  # Prendi solo le prime 'limit' condivisioni
        
        # Popola informazioni utente e libro per ogni condivisione
        await user_store.connect()
        await session_store_instance.connect()
        enriched_shares = []
        for share in shares:
            # Recupera info recipient
            recipient = await user_store.get_user_by_id(share.recipient_id)
            
            # Recupera info libro
            session = await get_session_async(session_store_instance, share.book_session_id, user_id=current_user.id)
            
            # Crea condivisione arricchita
            enriched_share = BookShare(
                id=share.id,
                book_session_id=share.book_session_id,
                owner_id=share.owner_id,
                recipient_id=share.recipient_id,
                status=share.status,
                created_at=share.created_at,
                updated_at=share.updated_at,
                owner_name=current_user.name,
                recipient_name=recipient.name if recipient else None,
                book_title=session.current_title if session else None,
            )
            enriched_shares.append(enriched_share)
        
        # Calcola total (approssimativo)
        total = skip + len(shares) + (1 if has_more else 0)
        
        return BookShareResponse(
            shares=enriched_shares,
            total=total,
            has_more=has_more,
        )
    except Exception as e:
        print(f"[BOOK SHARES API] ERRORE nel recupero libri condivisi con altri: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nel recupero dei libri condivisi con altri: {str(e)}",
        )


@router.patch("/shares/{share_id}", response_model=BookShare)
async def update_share_status(
    share_id: str,
    request: BookShareActionRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Accetta o rifiuta una condivisione di libro.
    
    Args:
        share_id: ID della condivisione
        request: Richiesta con azione (accept/decline)
        current_user: Utente corrente (da auth) - deve essere il destinatario
    
    Returns:
        BookShare aggiornata
    """
    book_share_store = get_book_share_store()
    notification_store = get_notification_store()
    user_store = get_user_store()
    session_store = get_session_store()
    
    try:
        await book_share_store.connect()
        
        # Recupera condivisione per verificare ownership
        shares = await book_share_store.get_user_shared_books(
            user_id=current_user.id,
            status="pending",
            limit=1000,  # Recupera tutte per trovare quella specifica
            skip=0,
        )
        
        share = None
        for s in shares:
            if s.id == share_id and s.recipient_id == current_user.id:
                share = s
                break
        
        if not share:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Condivisione non trovata o non autorizzata",
            )
        
        if share.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La condivisione non è in stato pending (stato attuale: {share.status})",
            )
        
        # Determina nuovo status basato sull'azione
        new_status = "accepted" if request.action == "accept" else "declined"
        
        # Aggiorna condivisione
        updated_share = await book_share_store.update_share_status(
            share_id=share_id,
            status=new_status,
            user_id=current_user.id,
        )
        
        if not updated_share:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Errore nell'aggiornamento della condivisione",
            )
        
        # Se accettata, crea notifica per l'owner originale
        if new_status == "accepted":
            await user_store.connect()
            owner = await user_store.get_user_by_id(share.owner_id)
            
            session_store_instance = get_session_store()
            await session_store_instance.connect()
            session = await get_session_async(session_store_instance, share.book_session_id, user_id=None)
            book_title = session.current_title if session else "Libro"
            
            if owner:
                await notification_store.connect()
                await notification_store.create_notification(
                    user_id=owner.id,
                    type="book_share_accepted",
                    title="Condivisione libro accettata",
                    message=f"{current_user.name} ha accettato la condivisione del libro '{book_title}'",
                    data={
                        "from_user_id": current_user.id,
                        "from_user_name": current_user.name,
                        "book_session_id": share.book_session_id,
                        "book_title": book_title,
                        "share_id": share_id,
                    },
                )
        
        print(f"[BOOK SHARES API] Condivisione {share_id} aggiornata a status: {new_status}", file=sys.stderr)
        
        return updated_share
    except HTTPException:
        raise
    except Exception as e:
        print(f"[BOOK SHARES API] ERRORE nell'aggiornamento condivisione: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nell'aggiornamento della condivisione: {str(e)}",
        )


@router.delete("/shares/{share_id}")
async def revoke_share(
    share_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Revoca una condivisione di libro (solo owner può revocare).
    
    Args:
        share_id: ID della condivisione
        current_user: Utente corrente (da auth) - deve essere l'owner
    
    Returns:
        Dict con success=True se revocata
    """
    book_share_store = get_book_share_store()
    
    try:
        await book_share_store.connect()
        
        success = await book_share_store.delete_book_share(share_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Condivisione non trovata o non autorizzata",
            )
        
        print(f"[BOOK SHARES API] Condivisione revocata: {share_id} da {current_user.id}", file=sys.stderr)
        
        return {"success": True, "message": "Condivisione revocata"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[BOOK SHARES API] ERRORE nella revoca condivisione: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nella revoca della condivisione: {str(e)}",
        )


@router.get("/{session_id}/shares", response_model=BookShareResponse)
async def get_book_shares(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Recupera tutte le condivisioni di un libro specifico (solo owner può vedere).
    
    Args:
        session_id: ID sessione del libro
        current_user: Utente corrente (da auth) - deve essere l'owner
    
    Returns:
        BookShareResponse con lista condivisioni del libro
    """
    book_share_store = get_book_share_store()
    user_store = get_user_store()
    session_store_instance = get_session_store()
    
    try:
        # Verifica ownership del libro
        await session_store_instance.connect()
        session = await get_session_async(session_store_instance, session_id, user_id=current_user.id)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Libro non trovato",
            )
        
        if session.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo il proprietario può vedere le condivisioni di un libro",
            )
        
        # Recupera tutte le condivisioni del libro
        await book_share_store.connect()
        shares = await book_share_store.get_all_shares_for_book(
            book_session_id=session_id,
            owner_id=current_user.id,
        )
        
        # Popola informazioni utente per ogni condivisione
        await user_store.connect()
        enriched_shares = []
        for share in shares:
            # Recupera info recipient
            recipient = await user_store.get_user_by_id(share.recipient_id)
            
            # Recupera info libro (owner può accedere)
            book_session = await get_session_async(session_store_instance, share.book_session_id, user_id=current_user.id)
            
            # Crea condivisione arricchita
            enriched_share = BookShare(
                id=share.id,
                book_session_id=share.book_session_id,
                owner_id=share.owner_id,
                recipient_id=share.recipient_id,
                status=share.status,
                created_at=share.created_at,
                updated_at=share.updated_at,
                owner_name=current_user.name,
                recipient_name=recipient.name if recipient else None,
                book_title=book_session.current_title if book_session else session.current_title if session else None,
            )
            enriched_shares.append(enriched_share)
        
        return BookShareResponse(
            shares=enriched_shares,
            total=len(enriched_shares),
            has_more=False,
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[BOOK SHARES API] ERRORE nel recupero condivisioni libro: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nel recupero delle condivisioni del libro: {str(e)}",
        )
