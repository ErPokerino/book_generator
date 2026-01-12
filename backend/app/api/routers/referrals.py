"""Router per sistema referral (inviti esterni)."""
import sys
import asyncio
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status, Depends, Query
from app.models import (
    Referral,
    ReferralRequest,
    ReferralStats,
    User,
)
from app.agent.referral_store import get_referral_store
from app.agent.user_store import get_user_store
from app.middleware.auth import get_current_user
from app.services.email_service import get_email_service


router = APIRouter(prefix="/api/referrals", tags=["referrals"])


@router.post("", response_model=Referral)
async def send_referral(
    request: ReferralRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Invia un invito referral a un nuovo utente (non ancora registrato).
    
    Args:
        request: Richiesta con email del destinatario
        current_user: Utente corrente (da auth) - chi invia l'invito
    
    Returns:
        Referral creato (status: pending)
    """
    referral_store = get_referral_store()
    user_store = get_user_store()
    email_service = get_email_service()
    
    try:
        # Normalizza email
        email = request.email.lower().strip()
        
        # Verifica formato email base
        if "@" not in email or "." not in email.split("@")[1]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email non valida",
            )
        
        # Verifica limite giornaliero PRIMA di controllare utente esistente (per evitare leak info)
        await referral_store.connect()
        can_send = await referral_store.check_daily_limit(current_user.id, max_per_day=10)
        
        if not can_send:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Hai raggiunto il limite giornaliero di inviti (10/giorno). Riprova domani.",
            )
        
        # Verifica che non stia invitando se stesso
        await user_store.connect()
        existing_user = await user_store.get_user_by_email(email)
        
        if existing_user:
            if existing_user.id == current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Non puoi invitare te stesso",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Questo utente è già registrato su NarrAI",
                )
        
        # Crea referral
        # Il referral_store gestirà eventuali duplicati
        referral = await referral_store.create_referral(
            referrer_id=current_user.id,
            invited_email=email,
            token_expiry_days=30,
        )
        
        # Popola nome referrer per risposta
        referral.referrer_name = current_user.name
        
        # Invia email referral (best-effort, non blocca se fallisce)
        try:
            email_sent = await asyncio.to_thread(
                email_service.send_referral_email,
                to_email=email,
                sender_name=current_user.name,
                token=referral.token,
            )
            if email_sent:
                print(f"[REFERRALS API] Email referral inviata a: {email}", file=sys.stderr)
            else:
                print(f"[REFERRALS API] WARNING: Email referral non inviata a {email} (credenziali SMTP mancanti)", file=sys.stderr)
        except Exception as email_error:
            # Log errore ma non bloccare la richiesta
            print(f"[REFERRALS API] WARNING: Errore invio email referral (non bloccante): {email_error}", file=sys.stderr)
        
        print(f"[REFERRALS API] Referral creato: {current_user.id} -> {email} (token: {referral.token[:8]}...)", file=sys.stderr)
        
        return referral
        
    except HTTPException:
        raise
    except ValueError as e:
        # Errore da referral_store (es: referral già esistente)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        print(f"[REFERRALS API] ERRORE nell'invio referral: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nell'invio dell'invito: {str(e)}",
        )


@router.get("", response_model=List[Referral])
async def get_my_referrals(
    limit: int = Query(50, ge=1, le=100, description="Numero massimo di referral da recuperare"),
    skip: int = Query(0, ge=0, description="Numero di referral da saltare (per paginazione)"),
    current_user: User = Depends(get_current_user),
):
    """
    Recupera tutti i referral inviati dall'utente corrente.
    
    Args:
        limit: Numero massimo di referral (default: 50, max: 100)
        skip: Numero di referral da saltare per paginazione (default: 0)
        current_user: Utente corrente (da auth)
    
    Returns:
        Lista di referral inviati
    """
    referral_store = get_referral_store()
    user_store = get_user_store()
    
    try:
        await referral_store.connect()
        referrals = await referral_store.get_referrals_by_user(
            referrer_id=current_user.id,
            limit=limit,
            skip=skip,
        )
        
        # Popola referrer_name per tutti i referral
        for referral in referrals:
            referral.referrer_name = current_user.name
        
        print(f"[REFERRALS API] Recuperati {len(referrals)} referral per utente {current_user.id}", file=sys.stderr)
        
        return referrals
    except HTTPException:
        # Mantieni status code originali (es. 401/403) invece di convertirli in 500
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"[REFERRALS API] ERRORE nel recupero referral: {error_msg}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        
        # Fornisci messaggio più dettagliato per debugging
        if "MongoDB" in error_msg or "connection" in error_msg.lower():
            detail_msg = f"Errore di connessione al database: {error_msg}"
        else:
            detail_msg = f"Errore nel recupero degli inviti: {error_msg}"
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail_msg,
        )


@router.get("/stats", response_model=ReferralStats)
async def get_referral_stats(
    current_user: User = Depends(get_current_user),
):
    """
    Recupera statistiche referral per l'utente corrente.
    
    Args:
        current_user: Utente corrente (da auth)
    
    Returns:
        Statistiche referral (total_sent, total_registered, pending)
    """
    referral_store = get_referral_store()
    
    try:
        await referral_store.connect()
        stats_dict = await referral_store.get_referral_stats(current_user.id)
        
        stats = ReferralStats(
            total_sent=stats_dict.get("total_sent", 0),
            total_registered=stats_dict.get("total_registered", 0),
            pending=stats_dict.get("pending", 0),
        )
        
        print(f"[REFERRALS API] Statistiche referral per {current_user.id}: {stats.total_sent} inviati, {stats.total_registered} registrati, {stats.pending} in attesa", file=sys.stderr)
        
        return stats
    except HTTPException:
        # Mantieni status code originali (es. 401/403) invece di convertirli in 500
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"[REFERRALS API] ERRORE nel recupero statistiche referral: {error_msg}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        
        # Fornisci messaggio più dettagliato per debugging
        if "MongoDB" in error_msg or "connection" in error_msg.lower():
            detail_msg = f"Errore di connessione al database: {error_msg}"
        else:
            detail_msg = f"Errore nel recupero delle statistiche referral: {error_msg}"
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail_msg,
        )
