"""Store MongoDB per referral (inviti esterni)."""
import os
import sys
import secrets
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from app.models import Referral


class ReferralStore:
    """Store MongoDB per gestione referral/inviti esterni."""
    
    def __init__(self, connection_string: str, database: str = "narrai", collection: str = "referrals"):
        """
        Inizializza il MongoDB referral store.
        
        Args:
            connection_string: MongoDB connection string
            database: Nome del database (default: "narrai")
            collection: Nome della collection (default: "referrals")
        """
        self.client: Optional[AsyncIOMotorClient] = None
        self.connection_string = connection_string
        self.database_name = database
        self.collection_name = collection
        self.db = None
        self.referrals_collection = None
        print(f"[ReferralStore] Inizializzato. DB: {database}, Collection: {collection}", file=sys.stderr)
    
    async def connect(self):
        """Connette al database MongoDB e crea gli indici."""
        if self.client is None:
            try:
                self.client = AsyncIOMotorClient(self.connection_string)
                self.db = self.client[self.database_name]
                self.referrals_collection = self.db[self.collection_name]
                
                # Crea indici per performance
                await self._create_indexes()
                
                print(f"[ReferralStore] Connesso a MongoDB: {self.database_name}", file=sys.stderr)
            except Exception as e:
                print(f"[ReferralStore] ERRORE nella connessione a MongoDB: {e}", file=sys.stderr)
                raise
    
    async def disconnect(self):
        """Chiude la connessione a MongoDB."""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            self.referrals_collection = None
            print(f"[ReferralStore] Disconnesso da MongoDB", file=sys.stderr)
    
    async def _create_indexes(self):
        """Crea indici per ottimizzare le query."""
        try:
            indexes = [
                IndexModel([("referrer_id", ASCENDING)]),
                IndexModel([("invited_email", ASCENDING)]),
                IndexModel([("status", ASCENDING)]),
                IndexModel([("token", ASCENDING)], unique=True),  # Token univoco
                IndexModel([("created_at", DESCENDING)]),
                # Compound index per query efficienti
                IndexModel([("referrer_id", ASCENDING), ("status", ASCENDING)]),
            ]
            await self.referrals_collection.create_indexes(indexes)
            print(f"[ReferralStore] Indici creati con successo", file=sys.stderr)
        except Exception as e:
            print(f"[ReferralStore] Avviso: errore nella creazione indici: {e}", file=sys.stderr)
    
    def _generate_token(self) -> str:
        """Genera token univoco per referral."""
        return secrets.token_urlsafe(32)  # Token sicuro 32 bytes
    
    def _referral_to_doc(self, referral: Referral) -> Dict[str, Any]:
        """Converte Referral in documento MongoDB."""
        doc = {
            "_id": referral.id,
            "referrer_id": referral.referrer_id,
            "invited_email": referral.invited_email.lower().strip(),
            "status": referral.status,
            "token": referral.token,
            "created_at": referral.created_at,
            "registered_at": referral.registered_at,
            "invited_user_id": referral.invited_user_id,
        }
        return doc
    
    @classmethod
    def _doc_to_referral(cls, doc: Dict[str, Any]) -> Referral:
        """Converte documento MongoDB in Referral."""
        return Referral(
            id=doc["_id"],
            referrer_id=doc["referrer_id"],
            invited_email=doc["invited_email"],
            status=doc["status"],
            token=doc["token"],
            created_at=doc.get("created_at", datetime.utcnow()),
            registered_at=doc.get("registered_at"),
            invited_user_id=doc.get("invited_user_id"),
        )
    
    async def create_referral(
        self,
        referrer_id: str,
        invited_email: str,
        token_expiry_days: int = 30,
    ) -> Referral:
        """
        Crea un nuovo referral.
        
        Args:
            referrer_id: ID utente che invia l'invito
            invited_email: Email destinatario
            token_expiry_days: Giorni di validità token (default: 30)
        
        Returns:
            Referral creato
        
        Raises:
            ValueError: Se referral già esistente per questa email
        """
        try:
            # Genera token univoco
            token = self._generate_token()
            # Verifica unicità token (retry se necessario)
            while await self.referrals_collection.find_one({"token": token}):
                token = self._generate_token()
            
            referral_id = secrets.token_urlsafe(16)
            now = datetime.utcnow()
            
            referral = Referral(
                id=referral_id,
                referrer_id=referrer_id,
                invited_email=invited_email.lower().strip(),
                status="pending",
                token=token,
                created_at=now,
                registered_at=None,
                invited_user_id=None,
            )
            
            doc = self._referral_to_doc(referral)
            await self.referrals_collection.insert_one(doc)
            
            print(f"[ReferralStore] Referral creato: {referral_id} per {invited_email}", file=sys.stderr)
            return referral
            
        except DuplicateKeyError as e:
            print(f"[ReferralStore] DuplicateKeyError: {e}", file=sys.stderr)
            # Verifica se è per email già invitata dallo stesso utente
            existing = await self.referrals_collection.find_one({
                "referrer_id": referrer_id,
                "invited_email": invited_email.lower().strip(),
            })
            if existing:
                # Controlla se è stato invitato oggi
                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                existing_created_at = existing.get("created_at")
                if existing_created_at and isinstance(existing_created_at, datetime) and existing_created_at >= today_start:
                    raise ValueError(f"Hai già invitato {invited_email} oggi. Puoi reinviare domani se necessario.")
                else:
                    # Invito vecchio (>24h), permette nuovo invito creando un nuovo referral
                    # Genera nuovo token e referral_id per reinvio
                    pass
            # Se non è per email duplicata, è per token duplicato (molto raro)
            raise ValueError("Token duplicato, riprova")
        except Exception as e:
            print(f"[ReferralStore] ERRORE creazione referral: {e}", file=sys.stderr)
            raise
    
    async def get_referral_by_token(self, token: str) -> Optional[Referral]:
        """Recupera referral per token."""
        try:
            doc = await self.referrals_collection.find_one({"token": token})
            if doc:
                return self._doc_to_referral(doc)
            return None
        except Exception as e:
            print(f"[ReferralStore] ERRORE get_referral_by_token: {e}", file=sys.stderr)
            raise
    
    async def mark_registered(self, token: str, invited_user_id: str) -> Optional[Referral]:
        """
        Marca referral come registrato quando l'utente si iscrive.
        
        Args:
            token: Token referral
            invited_user_id: ID utente registrato
        
        Returns:
            Referral aggiornato o None se non trovato
        """
        try:
            now = datetime.utcnow()
            result = await self.referrals_collection.find_one_and_update(
                {"token": token, "status": "pending"},
                {
                    "$set": {
                        "status": "registered",
                        "registered_at": now,
                        "invited_user_id": invited_user_id,
                    }
                },
                return_document=True,
            )
            
            if result:
                print(f"[ReferralStore] Referral marcato come registrato: {token} -> user {invited_user_id}", file=sys.stderr)
                return self._doc_to_referral(result)
            
            print(f"[ReferralStore] Referral non trovato o già registrato: {token}", file=sys.stderr)
            return None
            
        except Exception as e:
            print(f"[ReferralStore] ERRORE mark_registered: {e}", file=sys.stderr)
            raise
    
    async def get_referrals_by_user(self, referrer_id: str, limit: int = 50, skip: int = 0) -> List[Referral]:
        """Recupera tutti i referral inviati da un utente."""
        try:
            cursor = (
                self.referrals_collection
                .find({"referrer_id": referrer_id})
                .sort("created_at", DESCENDING)
                .skip(skip)
                .limit(limit)
            )
            
            referrals = []
            async for doc in cursor:
                referrals.append(self._doc_to_referral(doc))
            
            return referrals
        except Exception as e:
            print(f"[ReferralStore] ERRORE get_referrals_by_user: {e}", file=sys.stderr)
            raise
    
    async def get_referral_stats(self, referrer_id: str) -> Dict[str, int]:
        """
        Recupera statistiche referral per un utente.
        Conta solo gli inviti unici per email (prendendo l'ultimo invito per email).
        
        Returns:
            Dict con total_sent, total_registered, pending
        """
        try:
            # Pipeline per ottenere solo l'ultimo referral per ogni email
            # (l'email è già salvata in lowercase nel database)
            pipeline = [
                {"$match": {"referrer_id": referrer_id}},
                # Ordina per data creazione decrescente (più recente prima)
                {"$sort": {"created_at": -1}},
                # Raggruppa per email e prendi solo il primo (più recente)
                {
                    "$group": {
                        "_id": "$invited_email",
                        "latest_referral": {"$first": "$$ROOT"}
                    }
                },
                # Sostituisci la root con l'ultimo referral
                {"$replaceRoot": {"newRoot": "$latest_referral"}},
                # Ora raggruppa per status per contare
                {
                    "$group": {
                        "_id": "$status",
                        "count": {"$sum": 1},
                    }
                },
            ]
            
            results = await self.referrals_collection.aggregate(pipeline).to_list(length=100)
            
            stats = {
                "total_sent": 0,
                "total_registered": 0,
                "pending": 0,
            }
            
            # Conta gli inviti unici per status
            for result in results:
                status_key = result["_id"]
                count = result["count"]
                stats["total_sent"] += count
                
                if status_key == "registered":
                    stats["total_registered"] = count
                elif status_key == "pending":
                    stats["pending"] = count
            
            return stats
            
        except Exception as e:
            print(f"[ReferralStore] ERRORE get_referral_stats: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return {"total_sent": 0, "total_registered": 0, "pending": 0}
    
    async def check_daily_limit(self, referrer_id: str, max_per_day: int = 10) -> bool:
        """
        Verifica se l'utente ha raggiunto il limite giornaliero di inviti.
        
        Args:
            referrer_id: ID utente
            max_per_day: Limite massimo inviti al giorno (default: 10)
        
        Returns:
            True se può inviare, False se ha raggiunto il limite
        """
        try:
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            count = await self.referrals_collection.count_documents({
                "referrer_id": referrer_id,
                "created_at": {"$gte": today_start},
            })
            
            can_send = count < max_per_day
            if not can_send:
                print(f"[ReferralStore] Limite giornaliero raggiunto per {referrer_id}: {count}/{max_per_day}", file=sys.stderr)
            
            return can_send
            
        except Exception as e:
            print(f"[ReferralStore] ERRORE check_daily_limit: {e}", file=sys.stderr)
            # In caso di errore, permetti invio (fail-safe)
            return True
    
    async def expire_old_referrals(self, days: int = 30):
        """
        Marca come expired i referral più vecchi di N giorni.
        
        Args:
            days: Giorni di validità (default: 30)
        """
        try:
            expiry_date = datetime.utcnow() - timedelta(days=days)
            
            result = await self.referrals_collection.update_many(
                {
                    "status": "pending",
                    "created_at": {"$lt": expiry_date},
                },
                {
                    "$set": {
                        "status": "expired",
                    }
                },
            )
            
            if result.modified_count > 0:
                print(f"[ReferralStore] {result.modified_count} referral marcati come expired", file=sys.stderr)
                
        except Exception as e:
            print(f"[ReferralStore] ERRORE expire_old_referrals: {e}", file=sys.stderr)


# Istanza globale
_referral_store: Optional[ReferralStore] = None


def get_referral_store() -> ReferralStore:
    """Restituisce l'istanza globale del ReferralStore."""
    global _referral_store
    if _referral_store is None:
        mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        _referral_store = ReferralStore(connection_string=mongodb_uri)
    return _referral_store
