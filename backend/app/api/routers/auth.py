"""Router per autenticazione utenti."""
import os
import sys
import secrets
import asyncio
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, status, Response, Depends, Cookie
from fastapi.responses import JSONResponse
import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from app.models import (
    RegisterRequest,
    LoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserResponse,
    User,
)
from app.agent.user_store import get_user_store
from app.services.email_service import get_email_service
from app.middleware.auth import (
    create_session,
    delete_session,
    get_current_user,
    get_current_user_optional,
    require_admin,
)


class ResendVerificationRequest(BaseModel):
    """Richiesta reinvio email verifica."""
    email: str = Field(..., min_length=1)


class UpdateRoleRequest(BaseModel):
    """Richiesta aggiornamento ruolo utente."""
    role: str = Field(..., pattern="^(user|admin)$")


router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.get("/test")
async def auth_test():
    return {"status": "ok"}

# Password hashing - usa bcrypt direttamente per evitare problemi con passlib

def hash_password(password: str) -> str:
    """Hash della password usando bcrypt direttamente."""
    # Bcrypt ha un limite di 72 bytes per la password
    # Converti a bytes e tronca se necessario
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    # Genera salt e hash
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(password_bytes, salt)
    return password_hash.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica password usando bcrypt direttamente."""
    try:
        password_bytes = plain_password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def create_reset_token() -> str:
    """Genera token sicuro per reset password."""
    return secrets.token_urlsafe(32)


@router.post("/register")
async def register(request: RegisterRequest):
    """Registrazione nuovo utente con invio email di verifica e tracking referral."""
    try:
        user_store = get_user_store()
        email_service = get_email_service()

        # Assicurati che user_store sia connesso (reload/dev può lasciare la collection None)
        if user_store.client is None or user_store.users_collection is None:
            await user_store.connect()

        # GDPR: Verifica consensi obbligatori
        if not request.privacy_accepted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Devi accettare la Privacy Policy e i Termini di Servizio per registrarti",
            )
        if not request.data_processing_accepted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Devi acconsentire al trattamento dei dati tramite AI per utilizzare il servizio",
            )

        # Verifica email già esistente
        existing_user = await user_store.get_user_by_email(request.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email già registrata",
            )

        # Hash password
        password_hash = hash_password(request.password)
        
        # Timestamp consensi GDPR
        consent_timestamp = datetime.utcnow()

        # Crea utente (non verificato)
        user = await user_store.create_user(
            email=request.email,
            password_hash=password_hash,
            name=request.name,
            role="user",
            privacy_accepted_at=consent_timestamp,
            terms_accepted_at=consent_timestamp
        )
        print(f"[AUTH] Utente registrato (non verificato): {user.email}", file=sys.stderr)
        
        # Audit log registrazione
        try:
            from app.services.audit_service import get_audit_service
            audit_service = get_audit_service()
            await audit_service.log_account_created(
                user_id=user.id,
                user_email=user.email,
                referral_token=request.ref_token
            )
        except Exception as audit_error:
            print(f"[AUTH] Warning: audit log failed: {audit_error}", file=sys.stderr)
        
        # Tracking referral (se presente token)
        if request.ref_token:
            try:
                from app.agent.referral_store import get_referral_store
                referral_store = get_referral_store()
                await referral_store.connect()
                
                # Cerca referral per token
                referral = await referral_store.get_referral_by_token(request.ref_token)
                
                if referral and referral.status == "pending":
                    # Verifica che l'email corrisponda
                    if referral.invited_email.lower().strip() == request.email.lower().strip():
                        # Marca referral come registrato
                        await referral_store.mark_registered(request.ref_token, user.id)
                        print(f"[AUTH] Referral tracciato: token {request.ref_token[:8]}... -> utente {user.id}", file=sys.stderr)
                    else:
                        print(f"[AUTH] WARNING: Email referral ({referral.invited_email}) non corrisponde a email registrazione ({request.email})", file=sys.stderr)
                elif referral:
                    print(f"[AUTH] WARNING: Referral token {request.ref_token[:8]}... già processato o expired (status: {referral.status})", file=sys.stderr)
                else:
                    print(f"[AUTH] WARNING: Referral token {request.ref_token[:8]}... non trovato", file=sys.stderr)
                    
            except Exception as referral_error:
                # Errore nel tracking referral non blocca la registrazione
                print(f"[AUTH] WARNING: Errore tracking referral (non bloccante): {referral_error}", file=sys.stderr)
                import traceback
                traceback.print_exc()
        
        # Genera token di verifica
        verification_token = secrets.token_urlsafe(32)
        await user_store.set_verification_token(user.email, verification_token, expires_hours=24)
        
        # Invia email di verifica
        email_sent = email_service.send_verification_email(
            to_email=user.email,
            token=verification_token,
            user_name=user.name
        )
        
        if not email_sent:
            print(f"[AUTH] ATTENZIONE: Email di verifica non inviata a {user.email}", file=sys.stderr)
        
        # In dev mode, restituisci anche il token per testing
        is_dev = os.getenv("ENVIRONMENT") != "production"
        response_data = {
            "success": True,
            "message": f"Registrazione completata! Controlla la tua email ({user.email}) per verificare l'account.",
            "email": user.email,
            "requires_verification": True,
        }
        
        if is_dev:
            response_data["verification_token"] = verification_token
            response_data["dev_note"] = "Token visibile solo in dev mode"
        
        return response_data
        
    except HTTPException:
        raise
    except ValueError as e:
        print(f"[AUTH ERROR] ValueError in register: {e}", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        print(f"[AUTH ERROR] Exception in register: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore interno durante la registrazione",
        )

    
    # Verifica email già esistente
    # existing_user = await user_store.get_user_by_email(request.email)
    # if existing_user:
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="Email già registrata",
    #     )
    
    # Hash password
    # try:
    #     password_hash = hash_password(request.password)
    # except Exception as e:
    #     print(f"[AUTH ERROR] Errore hashing password: {e}", file=sys.stderr)
    #     import traceback
    #     traceback.print_exc()
    #     raise HTTPException(
    #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         detail=f"Errore interno (hashing): {str(e)}",
    #     )
    
    # Crea utente
    # try:
    #     user = await user_store.create_user(
    #         email=request.email,
    #         password_hash=password_hash,
    #         name=request.name,
    #         role="user"
    #     )
    #     print(f"[AUTH] Utente registrato: {user.email}", file=sys.stderr)
        
    #     return UserResponse(
    #         id=user.id,
    #         email=user.email,
    #         name=user.name,
    #         role=user.role,
    #         is_active=user.is_active,
    #         created_at=user.created_at,
    #     )
    # except Exception as e:
    #     print(f"[AUTH CRITICAL] Errore non gestito in register: {e}", file=sys.stderr)
    #     import traceback
    #     traceback.print_exc()
    #     raise HTTPException(
    #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         detail=f"Errore critico: {str(e)}"
    #     )


@router.post("/login")
async def login(request: LoginRequest, response: Response):
    """Login utente."""
    try:
        user_store = get_user_store()
        
        # Assicurati che user_store sia connesso
        if user_store.client is None or user_store.users_collection is None:
            await user_store.connect()
        
        # Recupera utente
        user = await user_store.get_user_by_email(request.email)
        if not user:
            print(f"[AUTH] Login fallito: utente {request.email} non trovato", file=sys.stderr)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email o password non corretti",
            )
        
        # Verifica password
        if not verify_password(request.password, user.password_hash):
            print(f"[AUTH] Login fallito: password errata per {request.email}", file=sys.stderr)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email o password non corretti",
            )
        
        # Verifica utente attivo
        if not user.is_active:
            print(f"[AUTH] Login fallito: utente {request.email} disattivato", file=sys.stderr)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Utente disattivato",
            )
        
        # Verifica email verificata
        if not user.is_verified:
            print(f"[AUTH] Login fallito: email {request.email} non verificata", file=sys.stderr)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="EMAIL_NOT_VERIFIED",  # Codice speciale per il frontend
            )
        
        # Crea sessione
        session_id = await create_session(user.id)
        
        # Imposta cookie httpOnly
        response.set_cookie(
            key="session_id",
            value=session_id,
            max_age=7 * 24 * 60 * 60,  # 7 giorni
            httponly=True,
            secure=os.getenv("ENVIRONMENT") == "production",  # HTTPS solo in produzione
            samesite="lax",
        )
        
        print(f"[AUTH] Login: {user.email}", file=sys.stderr)
        
        # Audit log login
        try:
            from app.services.audit_service import get_audit_service
            audit_service = get_audit_service()
            await audit_service.log_login(
                user_id=user.id,
                user_email=user.email,
                success=True
            )
        except Exception as audit_error:
            print(f"[AUTH] Warning: audit log failed: {audit_error}", file=sys.stderr)
        
        return {
            "success": True,
            "user": UserResponse(
                id=user.id,
                email=user.email,
                name=user.name,
                role=user.role,
                is_active=user.is_active,
                is_verified=user.is_verified,
                created_at=user.created_at,
            ),
        }
    
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"[AUTH ERROR] Errore nel login: {error_msg}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        
        # Fornisci messaggio più dettagliato
        if "MongoDB" in error_msg or "connection" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Errore di connessione al database: {error_msg}",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Errore interno durante il login: {error_msg}",
            )


@router.post("/logout")
async def logout(
    response: Response,
    auth_session_id: Optional[str] = Cookie(None, alias="session_id")
):
    """Logout utente."""
    if auth_session_id:
        await delete_session(auth_session_id)
    
    # Rimuovi cookie
    response.delete_cookie(key="session_id", httponly=True, samesite="lax")
    
    return {"success": True, "message": "Logout effettuato"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Ottiene informazioni utente corrente."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
    )


@router.get("/credits")
async def get_user_credits(current_user: User = Depends(get_current_user_optional)):
    """
    Ottiene i crediti disponibili per le modalità di generazione.
    I crediti si resettano automaticamente ogni lunedì.
    """
    from app.models import UserCreditsResponse, ModeCredits
    
    # Se l'utente non è autenticato, ritorna crediti default
    if not current_user:
        return UserCreditsResponse(
            credits=ModeCredits(),
            credits_reset_at=None,
            next_reset_at=datetime.utcnow(),
        )
    
    user_store = get_user_store()
    try:
        credits, credits_reset_at, next_reset_at = await user_store.get_user_credits(current_user.id)
        return UserCreditsResponse(
            credits=credits,
            credits_reset_at=credits_reset_at,
            next_reset_at=next_reset_at,
        )
    except ValueError as e:
        # Se l'utente non ha crediti, ritorna default invece di 404
        print(f"[AUTH] Utente {current_user.id} non ha crediti configurati, uso default: {e}", file=sys.stderr)
        return UserCreditsResponse(
            credits=ModeCredits(),
            credits_reset_at=None,
            next_reset_at=datetime.utcnow(),
        )
    except Exception as e:
        print(f"[AUTH] Errore nel recupero crediti: {e}", file=sys.stderr)
        # Fallback: ritorna crediti di default
        return UserCreditsResponse(
            credits=ModeCredits(),
            credits_reset_at=None,
            next_reset_at=datetime.utcnow(),
        )


class VerifyEmailRequest(BaseModel):
    """Richiesta verifica email."""
    token: str = Field(..., min_length=1)


@router.get("/verify/check")
async def check_verification_token(token: str):
    """
    Controlla se il token di verifica è valido senza invalidarlo.
    Usato dal frontend per mostrare lo stato prima della conferma.
    """
    user_store = get_user_store()
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token mancante",
        )
    
    # Controlla token senza invalidarlo
    check_result = await user_store.check_verification_token(token)
    
    if not check_result:
        # Token non trovato - potrebbe essere già stato usato
        # Verifica se esiste un utente già verificato con questo token (caso edge)
        # Per semplicità, restituiamo un errore generico
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token non valido o scaduto. Richiedi un nuovo link di verifica.",
        )
    
    # Se l'utente è già verificato, restituisci info positiva
    if check_result["already_verified"]:
        return {
            "success": True,
            "valid": True,
            "already_verified": True,
            "message": "Account già verificato! Puoi procedere al login.",
            "email": check_result["user"].email,
        }
    
    # Token valido ma non ancora verificato
    if check_result["valid"]:
        return {
            "success": True,
            "valid": True,
            "already_verified": False,
            "message": "Token valido. Clicca sul pulsante per confermare la verifica.",
            "email": check_result["user"].email,
        }
    
    # Token scaduto
    if check_result["expired"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token scaduto. Richiedi un nuovo link di verifica.",
        )
    
    # Caso generico
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Token non valido. Richiedi un nuovo link di verifica.",
    )


@router.post("/verify")
async def verify_email(request: VerifyEmailRequest):
    """
    Verifica email con token dal link.
    Questo endpoint invalida il token e marca l'utente come verificato.
    """
    user_store = get_user_store()
    if user_store.client is None or user_store.users_collection is None:
        await user_store.connect()
    
    if not request.token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token mancante",
        )
    
    # Verifica e attiva utente
    user = await user_store.verify_email(request.token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token non valido o scaduto. Richiedi un nuovo link di verifica.",
        )
    
    print(f"[AUTH] Email verificata per: {user.email}", file=sys.stderr)
    
    return {
        "success": True,
        "message": "Email verificata con successo! Ora puoi accedere.",
        "email": user.email,
    }


@router.post("/resend-verification")
async def resend_verification(request: ResendVerificationRequest):
    """Reinvia email di verifica."""
    user_store = get_user_store()
    email_service = get_email_service()

    if user_store.client is None or user_store.users_collection is None:
        await user_store.connect()
    
    # Recupera utente
    user = await user_store.get_user_by_email(request.email)
    
    if not user:
        # Non rivelare se l'email esiste (security)
        return {
            "success": True,
            "message": "Se l'email è registrata, riceverai un nuovo link di verifica.",
        }
    
    # Se già verificato
    if user.is_verified:
        return {
            "success": True,
            "message": "Email già verificata. Puoi accedere normalmente.",
            "already_verified": True,
        }
    
    # Genera nuovo token
    verification_token = secrets.token_urlsafe(32)
    await user_store.set_verification_token(user.email, verification_token, expires_hours=24)
    
    # Invia email
    email_sent = email_service.send_verification_email(
        to_email=user.email,
        token=verification_token,
        user_name=user.name
    )
    
    if email_sent:
        print(f"[AUTH] Email di verifica reinviata a: {user.email}", file=sys.stderr)
    else:
        print(f"[AUTH] ERRORE reinvio email a: {user.email}", file=sys.stderr)
    
    return {
        "success": True,
        "message": "Se l'email è registrata, riceverai un nuovo link di verifica.",
    }


@router.post("/password/forgot")
async def forgot_password(request: ForgotPasswordRequest):
    """Richiesta reset password."""
    user_store = get_user_store()

    if user_store.client is None or user_store.users_collection is None:
        await user_store.connect()
    
    user = await user_store.get_user_by_email(request.email)
    if not user:
        # Non rivelare se l'email esiste o no (security best practice)
        return {"success": True, "message": "Se l'email esiste, riceverai istruzioni per il reset"}
    
    # Genera token
    token = create_reset_token()
    
    # Salva token nel database
    await user_store.set_reset_token(request.email, token, expires_hours=24)
    
    # Invia email di reset password (best-effort, non blocca se fallisce)
    try:
        email_service = get_email_service()
        # Usa asyncio.to_thread per eseguire in background senza bloccare
        asyncio.create_task(
            asyncio.to_thread(
                email_service.send_password_reset_email,
                to_email=user.email,
                token=token,
                user_name=user.name,
            )
        )
    except Exception as email_error:
        # Log errore ma non bloccare la richiesta
        print(f"[AUTH] WARNING: Errore invio email reset (non bloccante): {email_error}", file=sys.stderr)
    
    # In dev mode, restituisci il token nella risposta (per testing)
    is_dev = os.getenv("ENVIRONMENT") != "production"
    
    if is_dev:
        print(f"[AUTH] Reset token per {request.email}: {token}", file=sys.stderr)
        return {
            "success": True, 
            "message": "Token generato (modalità sviluppo)",
            "token": token  # Solo in dev mode!
        }
    
    return {"success": True, "message": "Se l'email esiste, riceverai istruzioni per il reset"}


@router.post("/password/reset")
async def reset_password(request: ResetPasswordRequest):
    """Reset password con token."""
    user_store = get_user_store()

    if user_store.client is None or user_store.users_collection is None:
        await user_store.connect()
    
    # Verifica token
    user = await user_store.verify_reset_token(request.token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token non valido o scaduto",
        )
    
    # Hash nuova password
    password_hash = hash_password(request.new_password)
    
    # Aggiorna password
    success = await user_store.update_password(user.id, password_hash)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nell'aggiornamento password",
        )
    
    print(f"[AUTH] Password resettata per: {user.email}", file=sys.stderr)
    
    return {"success": True, "message": "Password aggiornata con successo"}


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    request: UpdateRoleRequest,
    current_user: User = Depends(require_admin)
):
    """
    Aggiorna il ruolo di un utente (solo admin).
    
    Args:
        user_id: ID dell'utente da modificare
        request: Richiesta con nuovo ruolo (user o admin)
    """
    user_store = get_user_store()

    if user_store.client is None or user_store.users_collection is None:
        await user_store.connect()
    
    # Verifica che l'utente esista
    target_user = await user_store.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utente non trovato",
        )
    
    # Valida ruolo
    if request.role not in ["user", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ruolo non valido. Deve essere 'user' o 'admin'",
        )
    
    # Aggiorna ruolo
    success = await user_store.update_user(user_id, {"role": request.role})
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nell'aggiornamento del ruolo",
        )
    
    print(f"[AUTH] Ruolo aggiornato per {target_user.email}: {request.role}", file=sys.stderr)
    
    return {
        "success": True,
        "message": f"Ruolo aggiornato a '{request.role}' per {target_user.email}",
        "user": {
            "id": target_user.id,
            "email": target_user.email,
            "name": target_user.name,
            "role": request.role,
        }
    }


@router.get("/users/by-email/{email}")
async def get_user_by_email_endpoint(
    email: str,
    current_user: User = Depends(require_admin)
):
    """
    Cerca un utente per email (solo admin).
    Utile per trovare user_id prima di modificare il ruolo.
    """
    user_store = get_user_store()

    if user_store.client is None or user_store.users_collection is None:
        await user_store.connect()
    
    user = await user_store.get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utente non trovato",
        )
    
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "created_at": user.created_at,
    }
