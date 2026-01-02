"""Router per autenticazione utenti."""
import os
import sys
import secrets
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, status, Response, Depends, Cookie
from fastapi.responses import JSONResponse
import bcrypt
from jose import JWTError, jwt
from app.models import (
    RegisterRequest,
    LoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserResponse,
    User,
)
from app.agent.user_store import get_user_store
from app.middleware.auth import (
    create_session,
    delete_session,
    get_current_user,
    get_current_user_optional,
    require_admin,
)

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


@router.post("/register", response_model=UserResponse)
async def register(request: RegisterRequest):
    """Registrazione nuovo utente."""
    user_store = get_user_store()
    
    # Verifica email già esistente
    existing_user = await user_store.get_user_by_email(request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email già registrata",
        )
    
    # Hash password
    password_hash = hash_password(request.password)
    
    # Crea utente
    try:
        user = await user_store.create_user(
            email=request.email,
            password_hash=password_hash,
            name=request.name,
            role="user"
        )
        print(f"[AUTH] Utente registrato: {user.email}", file=sys.stderr)
        
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        )
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
    user_store = get_user_store()
    
    # Recupera utente
    user = await user_store.get_user_by_email(request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o password non corretti",
        )
    
    # Verifica password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o password non corretti",
        )
    
    # Verifica utente attivo
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Utente disattivato",
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
    
    return {
        "success": True,
        "user": UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    }


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
        created_at=current_user.created_at,
    )


@router.post("/password/forgot")
async def forgot_password(request: ForgotPasswordRequest):
    """Richiesta reset password."""
    user_store = get_user_store()
    
    user = await user_store.get_user_by_email(request.email)
    if not user:
        # Non rivelare se l'email esiste o no (security best practice)
        return {"success": True, "message": "Se l'email esiste, riceverai istruzioni per il reset"}
    
    # Genera token
    token = create_reset_token()
    
    # Salva token nel database
    await user_store.set_reset_token(request.email, token, expires_hours=24)
    
    # TODO: Invia email con token (implementare quando SMTP configurato)
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
