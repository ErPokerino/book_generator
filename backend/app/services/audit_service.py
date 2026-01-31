"""
Servizio di Audit Logging per eventi GDPR-relevant.

Registra eventi critici per accountability e tracciabilita (GDPR Art. 5.2).
"""
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any, Literal
from motor.motor_asyncio import AsyncIOMotorClient


# Tipi di eventi auditabili
AuditEventType = Literal[
    # Autenticazione
    "login",
    "logout", 
    "login_failed",
    "password_reset_request",
    "password_reset_complete",
    "email_verification",
    
    # Account
    "account_created",
    "account_deleted",
    "profile_updated",
    "consent_updated",
    
    # Dati personali
    "data_export",
    "data_access",
    
    # Contenuti
    "book_created",
    "book_deleted",
    "book_shared",
    
    # Admin
    "admin_action",
    "retention_cleanup",
]


class AuditService:
    """Servizio per logging di eventi GDPR-relevant."""
    
    def __init__(self, mongo_uri: str):
        self.mongo_uri = mongo_uri
        self.client: Optional[AsyncIOMotorClient] = None
        self.audit_collection = None
    
    async def connect(self):
        """Connette al database MongoDB."""
        if self.client is None:
            self.client = AsyncIOMotorClient(self.mongo_uri)
            db = self.client.narrai
            self.audit_collection = db.audit_logs
            
            # Crea indici
            try:
                await self.audit_collection.create_index("timestamp")
                await self.audit_collection.create_index("user_id")
                await self.audit_collection.create_index("action")
                await self.audit_collection.create_index([("timestamp", -1), ("user_id", 1)])
            except Exception as e:
                print(f"[AuditService] Avviso creazione indici: {e}", file=sys.stderr)
    
    async def disconnect(self):
        """Chiude la connessione."""
        if self.client:
            self.client.close()
            self.client = None
            self.audit_collection = None
    
    async def log(
        self,
        action: AuditEventType,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True
    ):
        """
        Registra un evento di audit.
        
        Args:
            action: Tipo di evento
            user_id: ID utente (se autenticato)
            user_email: Email utente (per ricerca)
            ip_address: Indirizzo IP (anonimizzato dopo 90 giorni)
            user_agent: User-Agent del browser
            details: Dettagli aggiuntivi specifici per l'evento
            success: Se l'operazione è andata a buon fine
        """
        if self.audit_collection is None:
            await self.connect()
        
        try:
            log_entry = {
                "timestamp": datetime.utcnow(),
                "action": action,
                "user_id": user_id,
                "user_email": user_email,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "details": details or {},
                "success": success
            }
            
            await self.audit_collection.insert_one(log_entry)
            
            # Log anche su stderr per debugging
            print(f"[AUDIT] {action} - user: {user_email or user_id or 'anonymous'} - success: {success}", file=sys.stderr)
            
        except Exception as e:
            # Non far fallire l'operazione principale se il logging fallisce
            print(f"[AuditService] ERRORE logging: {e}", file=sys.stderr)
    
    async def log_login(
        self,
        user_id: str,
        user_email: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True
    ):
        """Registra un evento di login."""
        await self.log(
            action="login" if success else "login_failed",
            user_id=user_id if success else None,
            user_email=user_email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success
        )
    
    async def log_logout(
        self,
        user_id: str,
        user_email: str
    ):
        """Registra un evento di logout."""
        await self.log(
            action="logout",
            user_id=user_id,
            user_email=user_email
        )
    
    async def log_account_created(
        self,
        user_id: str,
        user_email: str,
        ip_address: Optional[str] = None,
        referral_token: Optional[str] = None
    ):
        """Registra la creazione di un account."""
        await self.log(
            action="account_created",
            user_id=user_id,
            user_email=user_email,
            ip_address=ip_address,
            details={
                "has_referral": bool(referral_token)
            }
        )
    
    async def log_account_deleted(
        self,
        user_id: str,
        user_email: str,
        books_deleted: int = 0,
        notifications_deleted: int = 0
    ):
        """Registra la cancellazione di un account (GDPR)."""
        await self.log(
            action="account_deleted",
            user_id=user_id,
            user_email=user_email,
            details={
                "books_deleted": books_deleted,
                "notifications_deleted": notifications_deleted,
                "gdpr_request": True
            }
        )
    
    async def log_data_export(
        self,
        user_id: str,
        user_email: str,
        ip_address: Optional[str] = None
    ):
        """Registra una richiesta di export dati (GDPR Art. 20)."""
        await self.log(
            action="data_export",
            user_id=user_id,
            user_email=user_email,
            ip_address=ip_address,
            details={
                "gdpr_article": "20",
                "type": "data_portability"
            }
        )
    
    async def log_consent_updated(
        self,
        user_id: str,
        user_email: str,
        consent_type: str,
        granted: bool
    ):
        """Registra un aggiornamento di consenso."""
        await self.log(
            action="consent_updated",
            user_id=user_id,
            user_email=user_email,
            details={
                "consent_type": consent_type,
                "granted": granted
            }
        )
    
    async def log_password_reset(
        self,
        user_email: str,
        stage: Literal["request", "complete"],
        ip_address: Optional[str] = None,
        success: bool = True
    ):
        """Registra una richiesta o completamento di reset password."""
        action = "password_reset_request" if stage == "request" else "password_reset_complete"
        await self.log(
            action=action,
            user_email=user_email,
            ip_address=ip_address,
            success=success
        )
    
    async def log_book_created(
        self,
        user_id: str,
        user_email: str,
        session_id: str,
        book_title: Optional[str] = None
    ):
        """Registra la creazione di un libro."""
        await self.log(
            action="book_created",
            user_id=user_id,
            user_email=user_email,
            details={
                "session_id": session_id,
                "book_title": book_title
            }
        )
    
    async def log_book_deleted(
        self,
        user_id: str,
        user_email: str,
        session_id: str,
        book_title: Optional[str] = None
    ):
        """Registra l'eliminazione di un libro."""
        await self.log(
            action="book_deleted",
            user_id=user_id,
            user_email=user_email,
            details={
                "session_id": session_id,
                "book_title": book_title
            }
        )
    
    async def log_admin_action(
        self,
        admin_id: str,
        admin_email: str,
        action_description: str,
        target_user_id: Optional[str] = None,
        target_user_email: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Registra un'azione amministrativa."""
        await self.log(
            action="admin_action",
            user_id=admin_id,
            user_email=admin_email,
            details={
                "action_description": action_description,
                "target_user_id": target_user_id,
                "target_user_email": target_user_email,
                **(details or {})
            }
        )
    
    async def log_retention_cleanup(
        self,
        results: Dict[str, Any]
    ):
        """Registra l'esecuzione del job di retention cleanup."""
        await self.log(
            action="retention_cleanup",
            details=results
        )
    
    async def get_user_audit_trail(
        self,
        user_id: str,
        limit: int = 100
    ) -> list:
        """
        Recupera la cronologia di audit per un utente.
        
        Args:
            user_id: ID utente
            limit: Numero massimo di record
        
        Returns:
            Lista di eventi audit
        """
        if self.audit_collection is None:
            await self.connect()
        
        cursor = self.audit_collection.find(
            {"user_id": user_id}
        ).sort("timestamp", -1).limit(limit)
        
        events = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            events.append(doc)
        
        return events


# Istanza globale
_audit_service: Optional[AuditService] = None


def get_audit_service() -> AuditService:
    """Restituisce l'istanza globale dell'AuditService."""
    global _audit_service
    if _audit_service is None:
        mongo_uri = os.getenv("MONGODB_URI")
        if not mongo_uri:
            raise ValueError("MONGODB_URI non configurato")
        _audit_service = AuditService(mongo_uri)
    return _audit_service


async def audit_log(
    action: AuditEventType,
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    success: bool = True
):
    """
    Funzione di utilità per logging rapido.
    Non solleva eccezioni se il logging fallisce.
    """
    try:
        service = get_audit_service()
        await service.log(
            action=action,
            user_id=user_id,
            user_email=user_email,
            ip_address=ip_address,
            details=details,
            success=success
        )
    except Exception as e:
        print(f"[AuditService] Errore utilità audit_log: {e}", file=sys.stderr)
