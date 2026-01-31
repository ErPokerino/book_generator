"""
Servizio per Data Retention (GDPR Art. 5.1.e - Limitazione della conservazione).

Implementa policy di retention automatica per eliminare dati non più necessari.
"""
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any


# Policy di retention (in giorni)
RETENTION_POLICIES = {
    # Token e sessioni (già implementati altrove, documentati qui per riferimento)
    "auth_sessions": 7,           # Sessioni di autenticazione: 7 giorni
    "password_reset_tokens": 1,   # Token reset password: 24 ore (scadono automaticamente)
    "verification_tokens": 1,     # Token verifica email: 24 ore (scadono automaticamente)
    
    # Dati applicativi
    "referrals_pending": 30,      # Inviti referral pendenti: 30 giorni
    "notifications_read": 90,     # Notifiche lette: 90 giorni
    "book_sessions_incomplete": 365,  # Sessioni incomplete: 1 anno
    
    # Audit e log
    "audit_logs": 730,            # Log di audit: 2 anni (requisito legale)
}


class RetentionService:
    """Servizio per eseguire la pulizia automatica dei dati scaduti."""
    
    def __init__(self):
        self.stats: Dict[str, int] = {}
    
    async def run_cleanup(self) -> Dict[str, Any]:
        """
        Esegue tutti i job di pulizia secondo le policy di retention.
        
        Returns:
            Dict con statistiche di pulizia per ogni categoria
        """
        print(f"[RetentionService] Avvio pulizia dati ({datetime.utcnow().isoformat()})", file=sys.stderr)
        
        results = {
            "started_at": datetime.utcnow().isoformat(),
            "cleaned": {},
            "errors": []
        }
        
        # 1. Pulizia notifiche lette
        try:
            cleaned = await self._cleanup_old_notifications()
            results["cleaned"]["notifications_read"] = cleaned
            print(f"[RetentionService] Notifiche lette pulite: {cleaned}", file=sys.stderr)
        except Exception as e:
            results["errors"].append(f"notifications: {str(e)}")
            print(f"[RetentionService] ERRORE pulizia notifiche: {e}", file=sys.stderr)
        
        # 2. Pulizia referral pendenti scaduti
        try:
            cleaned = await self._cleanup_expired_referrals()
            results["cleaned"]["referrals_pending"] = cleaned
            print(f"[RetentionService] Referral pendenti scaduti: {cleaned}", file=sys.stderr)
        except Exception as e:
            results["errors"].append(f"referrals: {str(e)}")
            print(f"[RetentionService] ERRORE pulizia referral: {e}", file=sys.stderr)
        
        # 3. Pulizia sessioni incomplete vecchie
        try:
            cleaned = await self._cleanup_old_incomplete_sessions()
            results["cleaned"]["book_sessions_incomplete"] = cleaned
            print(f"[RetentionService] Sessioni incomplete pulite: {cleaned}", file=sys.stderr)
        except Exception as e:
            results["errors"].append(f"sessions: {str(e)}")
            print(f"[RetentionService] ERRORE pulizia sessioni: {e}", file=sys.stderr)
        
        # 4. Pulizia token scaduti (password reset, verification)
        try:
            cleaned = await self._cleanup_expired_tokens()
            results["cleaned"]["expired_tokens"] = cleaned
            print(f"[RetentionService] Token scaduti puliti: {cleaned}", file=sys.stderr)
        except Exception as e:
            results["errors"].append(f"tokens: {str(e)}")
            print(f"[RetentionService] ERRORE pulizia token: {e}", file=sys.stderr)
        
        # 5. Pulizia audit log vecchi
        try:
            cleaned = await self._cleanup_old_audit_logs()
            results["cleaned"]["audit_logs"] = cleaned
            print(f"[RetentionService] Audit log puliti: {cleaned}", file=sys.stderr)
        except Exception as e:
            results["errors"].append(f"audit_logs: {str(e)}")
            print(f"[RetentionService] ERRORE pulizia audit log: {e}", file=sys.stderr)
        
        results["completed_at"] = datetime.utcnow().isoformat()
        
        total_cleaned = sum(results["cleaned"].values())
        print(f"[RetentionService] Pulizia completata. Totale record eliminati: {total_cleaned}", file=sys.stderr)
        
        return results
    
    async def _cleanup_old_notifications(self) -> int:
        """Elimina notifiche lette più vecchie della retention policy."""
        from app.agent.notification_store import get_notification_store
        
        store = get_notification_store()
        await store.connect()
        
        cutoff_date = datetime.utcnow() - timedelta(days=RETENTION_POLICIES["notifications_read"])
        
        if store.notifications_collection is None:
            return 0
        
        result = await store.notifications_collection.delete_many({
            "is_read": True,
            "created_at": {"$lt": cutoff_date}
        })
        
        return result.deleted_count
    
    async def _cleanup_expired_referrals(self) -> int:
        """Marca come scaduti i referral pendenti oltre la retention policy."""
        from app.agent.referral_store import get_referral_store
        
        store = get_referral_store()
        await store.connect()
        
        # Usa il metodo esistente
        await store.expire_old_referrals(days=RETENTION_POLICIES["referrals_pending"])
        
        # Ritorna un conteggio approssimativo
        return 0  # Il metodo esistente non restituisce un conteggio
    
    async def _cleanup_old_incomplete_sessions(self) -> int:
        """Elimina sessioni incomplete più vecchie della retention policy."""
        from app.agent.session_store import get_session_store
        
        store = get_session_store()
        await store.connect()
        
        cutoff_date = datetime.utcnow() - timedelta(days=RETENTION_POLICIES["book_sessions_incomplete"])
        
        # Per MongoSessionStore
        if hasattr(store, 'sessions_collection') and store.sessions_collection is not None:
            # Trova sessioni incomplete vecchie
            # Una sessione è incompleta se writing_progress è None o writing_progress.current_step < writing_progress.total_steps
            result = await store.sessions_collection.delete_many({
                "created_at": {"$lt": cutoff_date},
                "$or": [
                    {"writing_progress": None},
                    {"writing_progress.current_step": {"$lt": 1}},
                    # Sessioni in draft o outline che non sono mai state completate
                    {
                        "writing_progress.current_step": {"$exists": True},
                        "writing_progress.total_steps": {"$exists": True},
                        "$expr": {"$lt": ["$writing_progress.current_step", "$writing_progress.total_steps"]}
                    }
                ]
            })
            return result.deleted_count
        
        return 0
    
    async def _cleanup_expired_tokens(self) -> int:
        """Pulisce token scaduti (password reset, verification) dagli utenti."""
        from app.agent.user_store import get_user_store
        
        store = get_user_store()
        await store.connect()
        
        now = datetime.utcnow()
        
        if store.users_collection is None:
            return 0
        
        # Rimuovi token di password reset scaduti
        result1 = await store.users_collection.update_many(
            {
                "password_reset_expires": {"$lt": now}
            },
            {
                "$unset": {
                    "password_reset_token": "",
                    "password_reset_expires": ""
                }
            }
        )
        
        # Rimuovi token di verifica scaduti (ma non bloccare utenti non verificati)
        result2 = await store.users_collection.update_many(
            {
                "verification_expires": {"$lt": now}
            },
            {
                "$unset": {
                    "verification_token": "",
                    "verification_expires": ""
                }
            }
        )
        
        return result1.modified_count + result2.modified_count
    
    async def _cleanup_old_audit_logs(self) -> int:
        """Elimina log di audit più vecchi della retention policy."""
        from motor.motor_asyncio import AsyncIOMotorClient
        
        mongo_uri = os.getenv("MONGODB_URI")
        if not mongo_uri:
            return 0
        
        client = AsyncIOMotorClient(mongo_uri)
        db = client.narrai
        
        cutoff_date = datetime.utcnow() - timedelta(days=RETENTION_POLICIES["audit_logs"])
        
        try:
            # Anonimizza IP address nei log più vecchi di 90 giorni (prima di eliminare quelli vecchissimi)
            ip_cutoff = datetime.utcnow() - timedelta(days=90)
            await db.audit_logs.update_many(
                {
                    "timestamp": {"$lt": ip_cutoff},
                    "ip_address": {"$ne": "[ANONIMIZZATO]"}
                },
                {
                    "$set": {"ip_address": "[ANONIMIZZATO]"}
                }
            )
            
            # Elimina log più vecchi della retention policy
            result = await db.audit_logs.delete_many({
                "timestamp": {"$lt": cutoff_date}
            })
            
            return result.deleted_count
        except Exception as e:
            print(f"[RetentionService] Errore pulizia audit logs: {e}", file=sys.stderr)
            return 0
        finally:
            client.close()


# Istanza globale
_retention_service = None


def get_retention_service() -> RetentionService:
    """Restituisce l'istanza globale del RetentionService."""
    global _retention_service
    if _retention_service is None:
        _retention_service = RetentionService()
    return _retention_service


async def run_scheduled_cleanup():
    """
    Funzione di utilità per eseguire la pulizia programmata.
    Può essere chiamata da un cron job o scheduler.
    """
    service = get_retention_service()
    return await service.run_cleanup()
