"""Router per gestione crediti e acquisti pacchetti."""
import os
import sys
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Depends
from app.models import (
    CreditBalanceResponse,
    CreditPackagesResponse,
    CreditPurchaseRequest,
    CreditPurchaseResponse,
    CreditTransactionResponse,
    MODE_COSTS,
    DEFAULT_CREDITS,
)
from app.agent.credit_store import get_credit_store
from app.agent.user_store import get_user_store, UserStore
from app.middleware.auth import get_current_user, get_current_user_optional
from app.models import User


router = APIRouter(prefix="/api/credits", tags=["credits"])


@router.get("/balance", response_model=CreditBalanceResponse)
async def get_credit_balance(
    current_user: User = Depends(get_current_user_optional)
):
    """
    Ottiene il saldo crediti dell'utente corrente.
    
    Se l'utente non è autenticato, restituisce i crediti di default.
    """
    try:
        user_store = get_user_store()
        credit_store = get_credit_store()
        
        if not current_user:
            # Utente non autenticato: restituisce default
            next_monday = UserStore._get_next_monday()
            return CreditBalanceResponse(
                credits=DEFAULT_CREDITS,
                credits_reset_at=None,
                next_reset_at=next_monday,
                mode_costs=MODE_COSTS.copy(),
                total_purchased=0,
                total_consumed=0,
            )
        
        # Utente autenticato: ottiene crediti reali con lazy reset
        points, reset_at, next_reset = await user_store.get_user_points(current_user.id)
        stats = await credit_store.get_user_credit_stats(current_user.id)
        
        return CreditBalanceResponse(
            credits=points,
            credits_reset_at=reset_at,
            next_reset_at=next_reset,
            mode_costs=MODE_COSTS.copy(),
            total_purchased=stats.get("total_purchased", 0),
            total_consumed=stats.get("total_consumed", 0),
        )
        
    except Exception as e:
        print(f"[CREDITS] Errore get_credit_balance: {e}", file=sys.stderr)
        # Fallback con valori di default
        next_monday = UserStore._get_next_monday()
        return CreditBalanceResponse(
            credits=DEFAULT_CREDITS,
            credits_reset_at=None,
            next_reset_at=next_monday,
            mode_costs=MODE_COSTS.copy(),
            total_purchased=0,
            total_consumed=0,
        )


@router.get("/packages", response_model=CreditPackagesResponse)
async def get_credit_packages():
    """
    Ottiene la lista dei pacchetti crediti disponibili.
    
    Endpoint pubblico (non richiede autenticazione).
    """
    try:
        credit_store = get_credit_store()
        await credit_store.connect()
        
        # Prova a caricare da YAML se non ci sono pacchetti
        packages = await credit_store.get_active_packages()
        
        if not packages:
            # Carica pacchetti da configurazione YAML
            config_path = Path(__file__).parent.parent.parent.parent.parent / "config" / "credit_packages.yaml"
            if config_path.exists():
                await credit_store.load_packages_from_yaml(str(config_path))
                packages = await credit_store.get_active_packages()
        
        return CreditPackagesResponse(packages=packages)
        
    except Exception as e:
        print(f"[CREDITS] Errore get_credit_packages: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        # Restituisce lista vuota invece di errore
        return CreditPackagesResponse(packages=[])


@router.post("/purchase", response_model=CreditPurchaseResponse)
async def purchase_package(
    request: CreditPurchaseRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Acquista un pacchetto crediti.
    
    Per ora tutti i pacchetti sono gratuiti (free mode).
    In futuro sarà integrato con un gateway di pagamento.
    """
    try:
        credit_store = get_credit_store()
        await credit_store.connect()
        
        # Verifica che il pacchetto esista
        package = await credit_store.get_package_by_id(request.package_id)
        if not package:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pacchetto '{request.package_id}' non trovato"
            )
        
        if not package.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pacchetto '{package.name}' non più disponibile"
            )
        
        # Per ora tutti i pacchetti sono gratuiti - simula pagamento verificato
        # In futuro qui si integrerà con PaymentService
        from app.services.payment_service import get_payment_service
        payment_service = get_payment_service()
        
        payment_result = await payment_service.verify_payment(
            user_id=current_user.id,
            package_id=request.package_id,
            amount=package.price_eur
        )
        
        if not payment_result["verified"]:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Pagamento non verificato"
            )
        
        # Effettua l'acquisto
        success, message, new_balance, transaction = await credit_store.purchase_package(
            user_id=current_user.id,
            package_id=request.package_id,
            payment_verified=True
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        credits_added = package.credits + package.bonus_credits
        
        return CreditPurchaseResponse(
            success=True,
            message=message,
            credits_added=credits_added,
            new_balance=new_balance,
            transaction_id=transaction.id if transaction else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CREDITS] Errore purchase_package: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore durante l'acquisto: {str(e)}"
        )


@router.get("/transactions", response_model=CreditTransactionResponse)
async def get_transactions(
    skip: int = 0,
    limit: int = 20,
    tx_type: str = None,
    current_user: User = Depends(get_current_user)
):
    """
    Ottiene lo storico delle transazioni crediti dell'utente.
    
    Args:
        skip: Offset per paginazione (default: 0)
        limit: Numero massimo di transazioni (default: 20, max: 100)
        tx_type: Filtra per tipo (purchase, consumption, bonus, refund, reset)
    """
    try:
        # Limita il massimo di risultati
        if limit > 100:
            limit = 100
        if limit < 1:
            limit = 1
        
        credit_store = get_credit_store()
        await credit_store.connect()
        
        transactions, total = await credit_store.get_user_transactions(
            user_id=current_user.id,
            skip=skip,
            limit=limit,
            tx_type=tx_type
        )
        
        has_more = (skip + len(transactions)) < total
        
        return CreditTransactionResponse(
            transactions=transactions,
            total=total,
            has_more=has_more
        )
        
    except Exception as e:
        print(f"[CREDITS] Errore get_transactions: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore durante il recupero delle transazioni: {str(e)}"
        )


@router.post("/reload-packages")
async def reload_packages(
    current_user: User = Depends(get_current_user)
):
    """
    Ricarica i pacchetti crediti dal file YAML di configurazione.
    
    Solo per admin.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accesso riservato agli amministratori"
        )
    
    try:
        credit_store = get_credit_store()
        await credit_store.connect()
        
        config_path = Path(__file__).parent.parent.parent.parent.parent / "config" / "credit_packages.yaml"
        
        if not config_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File configurazione non trovato: {config_path}"
            )
        
        count = await credit_store.load_packages_from_yaml(str(config_path))
        
        return {
            "success": True,
            "message": f"Caricati {count} pacchetti",
            "packages_loaded": count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CREDITS] Errore reload_packages: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore durante il ricaricamento: {str(e)}"
        )
