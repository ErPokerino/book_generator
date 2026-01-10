"""Router per connessioni tra utenti."""
import sys
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query
from app.models import (
    Connection,
    ConnectionRequest,
    ConnectionResponse,
    UserSearchResponse,
    UserResponse,
    User,
)
from app.agent.connection_store import get_connection_store
from app.agent.notification_store import get_notification_store
from app.agent.user_store import get_user_store
from app.middleware.auth import get_current_user


router = APIRouter(prefix="/api/connections", tags=["connections"])


@router.get("/search", response_model=UserSearchResponse)
async def search_user(
    email: str = Query(..., min_length=1, description="Email dell'utente da cercare"),
    current_user: User = Depends(get_current_user),
):
    """
    Cerca un utente per email e restituisce informazioni sulla connessione esistente.
    
    Args:
        email: Email dell'utente da cercare
        current_user: Utente corrente (da auth)
    
    Returns:
        UserSearchResponse con info utente e stato connessione
    """
    user_store = get_user_store()
    connection_store = get_connection_store()
    
    try:
        # Normalizza email (lowercase, strip)
        email = email.lower().strip()
        
        # Non può cercare se stesso
        if email == current_user.email.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Non puoi cercare te stesso",
            )
        
        # Cerca utente
        await user_store.connect()
        target_user = await user_store.get_user_by_email(email)
        
        if not target_user:
            return UserSearchResponse(
                found=False,
                user=None,
                is_connected=False,
                has_pending_request=False,
                pending_request_from_me=False,
                connection_id=None,
            )
        
        # Verifica connessione esistente
        await connection_store.connect()
        connection = await connection_store.get_connection(current_user.id, target_user.id)
        
        if connection:
            is_connected = connection.status == "accepted"
            has_pending_request = connection.status == "pending"
            pending_request_from_me = connection.from_user_id == current_user.id
            
            return UserSearchResponse(
                found=True,
                user=UserResponse(
                    id=target_user.id,
                    email=target_user.email,
                    name=target_user.name,
                    role=target_user.role,
                    is_active=target_user.is_active,
                    is_verified=target_user.is_verified,
                    created_at=target_user.created_at,
                ),
                is_connected=is_connected,
                has_pending_request=has_pending_request,
                pending_request_from_me=pending_request_from_me,
                connection_id=connection.id,
            )
        else:
            return UserSearchResponse(
                found=True,
                user=UserResponse(
                    id=target_user.id,
                    email=target_user.email,
                    name=target_user.name,
                    role=target_user.role,
                    is_active=target_user.is_active,
                    is_verified=target_user.is_verified,
                    created_at=target_user.created_at,
                ),
                is_connected=False,
                has_pending_request=False,
                pending_request_from_me=False,
                connection_id=None,
            )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONNECTIONS API] ERRORE nella ricerca utente: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nella ricerca utente: {str(e)}",
        )


@router.get("", response_model=ConnectionResponse)
async def get_connections(
    status: Optional[str] = Query(default=None, description="Filtra per status (pending, accepted)"),
    limit: int = Query(default=50, ge=1, le=100, description="Numero massimo di connessioni"),
    skip: int = Query(default=0, ge=0, description="Numero di connessioni da saltare"),
    include_user_info: bool = Query(default=True, description="Includi informazioni utente nelle connessioni"),
    current_user: User = Depends(get_current_user),
):
    """
    Recupera le connessioni dell'utente corrente.
    
    Args:
        status: Filtra per status (opzionale)
        limit: Numero massimo di connessioni (1-100, default: 50)
        skip: Numero di connessioni da saltare (default: 0)
        include_user_info: Se True, include informazioni utente (per ora non implementato, solo struttura)
        current_user: Utente corrente (da auth)
    
    Returns:
        ConnectionResponse con lista connessioni
    """
    connection_store = get_connection_store()
    
    try:
        await connection_store.connect()
        
        # Recupera connessioni (limit + 1 per verificare se ci sono altre)
        all_connections = await connection_store.get_user_connections(
            user_id=current_user.id,
            status=status,
            limit=limit + 1,
            skip=skip,
        )
        
        # Determina se ci sono altre connessioni
        has_more = len(all_connections) > limit
        connections = all_connections[:limit]  # Prendi solo le prime 'limit' connessioni
        
        # Popola informazioni utente per ogni connessione
        user_store = get_user_store()
        await user_store.connect()
        enriched_connections = []
        for conn in connections:
            # Recupera info utente per from e to
            from_user = await user_store.get_user_by_id(conn.from_user_id)
            to_user = await user_store.get_user_by_id(conn.to_user_id)
            
            # Crea connessione arricchita con informazioni utente
            enriched_conn = Connection(
                id=conn.id,
                from_user_id=conn.from_user_id,
                to_user_id=conn.to_user_id,
                status=conn.status,
                created_at=conn.created_at,
                updated_at=conn.updated_at,
                from_user_name=from_user.name if from_user else None,
                to_user_name=to_user.name if to_user else None,
                from_user_email=from_user.email if from_user else None,
                to_user_email=to_user.email if to_user else None,
            )
            enriched_connections.append(enriched_conn)
        
        # Calcola total (approssimativo)
        total = skip + len(connections) + (1 if has_more else 0)
        
        return ConnectionResponse(
            connections=enriched_connections,
            total=total,
            has_more=has_more,
        )
    except Exception as e:
        print(f"[CONNECTIONS API] ERRORE nel recupero connessioni: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nel recupero delle connessioni: {str(e)}",
        )


@router.get("/pending-count")
async def get_pending_connections_count(
    current_user: User = Depends(get_current_user),
):
    """
    Recupera solo il conteggio delle richieste di connessione pendenti incoming (per badge).
    Endpoint ottimizzato per polling frequente.
    IMPORTANTE: Questo endpoint deve essere definito PRIMA di /pending per evitare conflitti di routing.
    
    Args:
        current_user: Utente corrente (da auth)
    
    Returns:
        Dict con pending_count (richieste in arrivo)
    """
    connection_store = get_connection_store()
    
    try:
        await connection_store.connect()
        pending_requests = await connection_store.get_pending_requests(
            user_id=current_user.id,
            incoming_only=True,  # Solo richieste in arrivo
        )
        return {"pending_count": len(pending_requests)}
    except Exception as e:
        print(f"[CONNECTIONS API] ERRORE nel recupero conteggio richieste pendenti: {e}", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nel recupero del conteggio: {str(e)}",
        )


@router.get("/pending", response_model=ConnectionResponse)
async def get_pending_requests(
    incoming_only: bool = Query(default=False, description="Se True, solo richieste in arrivo"),
    current_user: User = Depends(get_current_user),
):
    """
    Recupera le richieste pendenti dell'utente corrente.
    
    Args:
        incoming_only: Se True, solo richieste in arrivo (to_user_id = current_user)
        current_user: Utente corrente (da auth)
    
    Returns:
        ConnectionResponse con lista richieste pendenti
    """
    connection_store = get_connection_store()
    
    try:
        await connection_store.connect()
        
        connections = await connection_store.get_pending_requests(
            user_id=current_user.id,
            incoming_only=incoming_only,
        )
        
        # Popola informazioni utente per ogni connessione
        user_store = get_user_store()
        await user_store.connect()
        enriched_connections = []
        for conn in connections:
            # Recupera info utente
            from_user = await user_store.get_user_by_id(conn.from_user_id)
            to_user = await user_store.get_user_by_id(conn.to_user_id)
            
            # Crea connessione arricchita
            enriched_conn = Connection(
                id=conn.id,
                from_user_id=conn.from_user_id,
                to_user_id=conn.to_user_id,
                status=conn.status,
                created_at=conn.created_at,
                updated_at=conn.updated_at,
                from_user_name=from_user.name if from_user else None,
                to_user_name=to_user.name if to_user else None,
                from_user_email=from_user.email if from_user else None,
                to_user_email=to_user.email if to_user else None,
            )
            enriched_connections.append(enriched_conn)
        
        return ConnectionResponse(
            connections=enriched_connections,
            total=len(enriched_connections),
            has_more=False,
        )
    except Exception as e:
        print(f"[CONNECTIONS API] ERRORE nel recupero richieste pendenti: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nel recupero delle richieste pendenti: {str(e)}",
        )


@router.post("", response_model=Connection)
async def send_connection_request(
    request: ConnectionRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Invia una richiesta di connessione a un utente.
    
    Args:
        request: Richiesta con email del destinatario
        current_user: Utente corrente (da auth)
    
    Returns:
        Connection creata (status: pending)
    """
    user_store = get_user_store()
    connection_store = get_connection_store()
    notification_store = get_notification_store()
    
    try:
        # Normalizza email
        email = request.email.lower().strip()
        
        # Verifica che non stia cercando se stesso
        if email == current_user.email.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Non puoi inviare una richiesta di connessione a te stesso",
            )
        
        # Cerca utente destinatario
        await user_store.connect()
        target_user = await user_store.get_user_by_email(email)
        
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utente non trovato",
            )
        
        # Verifica che non esista già una connessione
        await connection_store.connect()
        existing_connection = await connection_store.get_connection(current_user.id, target_user.id)
        
        if existing_connection:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connessione già esistente con stato: {existing_connection.status}",
            )
        
        # Crea connessione PENDING
        connection = await connection_store.create_connection(
            from_user_id=current_user.id,
            to_user_id=target_user.id,
            status="pending",
        )
        
        # Crea notifica per il destinatario
        await notification_store.connect()
        await notification_store.create_notification(
            user_id=target_user.id,
            type="connection_request",
            title="Nuova richiesta di connessione",
            message=f"{current_user.name} vuole connettersi con te",
            data={
                "from_user_id": current_user.id,
                "from_user_name": current_user.name,
                "connection_id": connection.id,
            },
        )
        
        print(f"[CONNECTIONS API] Richiesta di connessione inviata: {current_user.id} -> {target_user.id}", file=sys.stderr)
        
        return connection
    except HTTPException:
        raise
    except ValueError as e:
        # Errore da connection_store (es: connessione già esistente)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        print(f"[CONNECTIONS API] ERRORE nell'invio richiesta connessione: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nell'invio della richiesta di connessione: {str(e)}",
        )


@router.patch("/{connection_id}/accept", response_model=Connection)
async def accept_connection(
    connection_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Accetta una richiesta di connessione.
    
    Args:
        connection_id: ID della connessione
        current_user: Utente corrente (da auth) - deve essere il destinatario
    
    Returns:
        Connection aggiornata (status: accepted)
    """
    connection_store = get_connection_store()
    notification_store = get_notification_store()
    user_store = get_user_store()
    
    try:
        await connection_store.connect()
        
        # Recupera connessione per verificare ownership e ottenere info mittente
        connections = await connection_store.get_user_connections(
            user_id=current_user.id,
            status="pending",
            limit=1000,  # Recupera tutte per trovare quella specifica
            skip=0,
        )
        
        connection = None
        for conn in connections:
            if conn.id == connection_id and conn.to_user_id == current_user.id:
                connection = conn
                break
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Richiesta di connessione non trovata o non autorizzata",
            )
        
        if connection.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La connessione non è in stato pending (stato attuale: {connection.status})",
            )
        
        # Aggiorna connessione a ACCEPTED
        updated_connection = await connection_store.update_connection_status(
            connection_id=connection_id,
            status="accepted",
            user_id=current_user.id,
        )
        
        if not updated_connection:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Errore nell'aggiornamento della connessione",
            )
        
        # Recupera info mittente originale per la notifica
        await user_store.connect()
        from_user = await user_store.get_user_by_id(connection.from_user_id)
        
        if from_user:
            # Crea notifica per il mittente originale che la richiesta è stata accettata
            await notification_store.connect()
            await notification_store.create_notification(
                user_id=from_user.id,
                type="connection_accepted",
                title="Richiesta di connessione accettata",
                message=f"{current_user.name} ha accettato la tua richiesta di connessione",
                data={
                    "from_user_id": current_user.id,
                    "from_user_name": current_user.name,
                    "connection_id": connection_id,
                },
            )
        
        print(f"[CONNECTIONS API] Connessione accettata: {connection_id}", file=sys.stderr)
        
        return updated_connection
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONNECTIONS API] ERRORE nell'accettazione connessione: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nell'accettazione della connessione: {str(e)}",
        )


@router.delete("/{connection_id}")
async def delete_connection(
    connection_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Elimina una connessione (annulla richiesta pendente o rimuove connessione accettata).
    
    Args:
        connection_id: ID della connessione
        current_user: Utente corrente (da auth) - deve essere parte della connessione
    
    Returns:
        Dict con success=True se eliminata
    """
    connection_store = get_connection_store()
    
    try:
        await connection_store.connect()
        
        success = await connection_store.delete_connection(connection_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connessione non trovata o non autorizzata",
            )
        
        print(f"[CONNECTIONS API] Connessione eliminata: {connection_id} da {current_user.id}", file=sys.stderr)
        
        return {"success": True, "message": "Connessione eliminata"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONNECTIONS API] ERRORE nell'eliminazione connessione: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nell'eliminazione della connessione: {str(e)}",
        )


