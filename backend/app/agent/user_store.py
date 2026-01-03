"""Store MongoDB per utenti."""
import os
import sys
from typing import Optional
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING
from pymongo.errors import DuplicateKeyError
from app.models import User


class UserStore:
    """Store MongoDB per gestione utenti."""
    
    def __init__(self, connection_string: str, database: str = "narrai", collection: str = "users"):
        """
        Inizializza il MongoDB user store.
        
        Args:
            connection_string: MongoDB connection string
            database: Nome del database (default: "narrai")
            collection: Nome della collection (default: "users")
        """
        self.client: Optional[AsyncIOMotorClient] = None
        self.connection_string = connection_string
        self.database_name = database
        self.collection_name = collection
        self.db = None
        self.users_collection = None
        print(f"[UserStore] Inizializzato. DB: {database}, Collection: {collection}", file=sys.stderr)
    
    async def connect(self):
        """Connette al database MongoDB e crea gli indici."""
        if self.client is None:
            try:
                self.client = AsyncIOMotorClient(self.connection_string)
                self.db = self.client[self.database_name]
                self.users_collection = self.db[self.collection_name]
                
                # Crea indici per performance
                await self._create_indexes()
                
                print(f"[UserStore] Connesso a MongoDB: {self.database_name}", file=sys.stderr)
            except Exception as e:
                print(f"[UserStore] ERRORE nella connessione a MongoDB: {e}", file=sys.stderr)
                raise
    
    async def disconnect(self):
        """Chiude la connessione a MongoDB."""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            self.users_collection = None
            print(f"[UserStore] Disconnesso da MongoDB", file=sys.stderr)
    
    async def _create_indexes(self):
        """Crea indici per ottimizzare le query."""
        try:
            indexes = [
                IndexModel([("email", ASCENDING)], unique=True),
                IndexModel([("role", ASCENDING)]),
                IndexModel([("created_at", ASCENDING)]),
            ]
            await self.users_collection.create_indexes(indexes)
            print(f"[UserStore] Indici creati con successo", file=sys.stderr)
        except Exception as e:
            print(f"[UserStore] Avviso: errore nella creazione indici: {e}", file=sys.stderr)
    
    def _user_to_doc(self, user: User) -> dict:
        """Converte User in documento MongoDB."""
        doc = {
            "_id": user.id,
            "email": user.email,
            "password_hash": user.password_hash,
            "name": user.name,
            "role": user.role,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }
        if user.password_reset_token:
            doc["password_reset_token"] = user.password_reset_token
        if user.password_reset_expires:
            doc["password_reset_expires"] = user.password_reset_expires
        if user.verification_token:
            doc["verification_token"] = user.verification_token
        if user.verification_expires:
            doc["verification_expires"] = user.verification_expires
        return doc
    
    @classmethod
    def _doc_to_user(cls, doc: dict) -> User:
        """Converte documento MongoDB in User."""
        return User(
            id=doc["_id"],
            email=doc["email"],
            password_hash=doc["password_hash"],
            name=doc["name"],
            role=doc.get("role", "user"),
            is_active=doc.get("is_active", True),
            is_verified=doc.get("is_verified", False),
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
            password_reset_token=doc.get("password_reset_token"),
            password_reset_expires=doc.get("password_reset_expires"),
            verification_token=doc.get("verification_token"),
            verification_expires=doc.get("verification_expires"),
        )
    
    async def create_user(self, email: str, password_hash: str, name: str, role: str = "user") -> User:
        """
        Crea un nuovo utente.
        
        Args:
            email: Email utente (deve essere unico)
            password_hash: Hash della password
            name: Nome utente
            role: Ruolo (default: "user")
        
        Returns:
            User creato
        
        Raises:
            ValueError: Se email già esistente
        """
        import uuid
        user_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        user = User(
            id=user_id,
            email=email.lower().strip(),
            password_hash=password_hash,
            name=name.strip(),
            role=role,
            is_active=True,
            is_verified=False,
            created_at=now,
            updated_at=now,
        )
        
        doc = self._user_to_doc(user)
        
        try:
            print(f"[UserStore] Tentativo inserimento utente: {email}", file=sys.stderr)
            await self.users_collection.insert_one(doc)
            print(f"[UserStore] Utente creato: {email}", file=sys.stderr)
            return user
        except DuplicateKeyError:
            print(f"[UserStore] DuplicateKeyError per: {email}", file=sys.stderr)
            raise ValueError(f"Email {email} già registrata")
        except Exception as e:
            print(f"[UserStore] ERRORE GRAVE insert_one: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            raise
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Recupera utente per email."""
        try:
            print(f"[UserStore] Cerco utente: {email}", file=sys.stderr)
            doc = await self.users_collection.find_one({"email": email.lower().strip()})
            print(f"[UserStore] Utente trovato: {bool(doc)}", file=sys.stderr)
            if doc:
                return self._doc_to_user(doc)
            return None
        except Exception as e:
            print(f"[UserStore] ERRORE get_user_by_email: {e}", file=sys.stderr)
            raise
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Recupera utente per ID."""
        doc = await self.users_collection.find_one({"_id": user_id})
        if doc:
            return self._doc_to_user(doc)
        return None
    
    async def update_password(self, user_id: str, new_password_hash: str) -> bool:
        """
        Aggiorna password utente.
        
        Returns:
            True se aggiornato con successo
        """
        result = await self.users_collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "password_hash": new_password_hash,
                    "updated_at": datetime.utcnow(),
                    "password_reset_token": None,
                    "password_reset_expires": None,
                }
            }
        )
        return result.modified_count > 0
    
    async def set_reset_token(self, email: str, token: str, expires_hours: int = 24) -> bool:
        """
        Imposta token per reset password.
        
        Args:
            email: Email utente
            token: Token di reset
            expires_hours: Ore di validità (default: 24)
        
        Returns:
            True se impostato con successo
        """
        expires = datetime.utcnow() + timedelta(hours=expires_hours)
        result = await self.users_collection.update_one(
            {"email": email.lower().strip()},
            {
                "$set": {
                    "password_reset_token": token,
                    "password_reset_expires": expires,
                    "updated_at": datetime.utcnow(),
                }
            }
        )
        return result.modified_count > 0
    
    async def verify_reset_token(self, token: str) -> Optional[User]:
        """
        Verifica token reset password e restituisce utente se valido.
        
        Returns:
            User se token valido, None altrimenti
        """
        doc = await self.users_collection.find_one({
            "password_reset_token": token,
            "password_reset_expires": {"$gt": datetime.utcnow()}
        })
        if doc:
            return self._doc_to_user(doc)
        return None
    
    async def get_all_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """Recupera tutti gli utenti (per admin)."""
        cursor = self.users_collection.find().skip(skip).limit(limit).sort("created_at", -1)
        users = []
        async for doc in cursor:
            users.append(self._doc_to_user(doc))
        return users
    
    async def update_user(self, user_id: str, updates: dict) -> bool:
        """
        Aggiorna utente.
        
        Args:
            user_id: ID utente
            updates: Dict con campi da aggiornare (role, is_active, name)
        
        Returns:
            True se aggiornato con successo
        """
        updates["updated_at"] = datetime.utcnow()
        result = await self.users_collection.update_one(
            {"_id": user_id},
            {"$set": updates}
        )
        return result.modified_count > 0
    
    async def set_verification_token(self, email: str, token: str, expires_hours: int = 24) -> bool:
        """
        Imposta token per verifica email.
        
        Args:
            email: Email utente
            token: Token di verifica
            expires_hours: Ore di validità (default: 24)
        
        Returns:
            True se impostato con successo
        """
        # Auto-connect se non connesso
        if self.users_collection is None:
            await self.connect()
        expires = datetime.utcnow() + timedelta(hours=expires_hours)
        result = await self.users_collection.update_one(
            {"email": email.lower().strip()},
            {
                "$set": {
                    "verification_token": token,
                    "verification_expires": expires,
                    "updated_at": datetime.utcnow(),
                }
            }
        )
        return result.modified_count > 0
    
    async def check_verification_token(self, token: str) -> Optional[dict]:
        """
        Controlla se il token di verifica è valido senza invalidarlo.
        
        Returns:
            Dict con informazioni sul token:
            - "valid": bool - se il token è valido
            - "user": User - utente associato (se trovato)
            - "already_verified": bool - se l'utente è già verificato
            - "expired": bool - se il token è scaduto
        """
        # Auto-connect se non connesso
        if self.users_collection is None:
            await self.connect()
        
        # Prima cerca utente con token valido
        doc = await self.users_collection.find_one({
            "verification_token": token,
            "verification_expires": {"$gt": datetime.utcnow()}
        })
        
        if doc:
            user = self._doc_to_user(doc)
            return {
                "valid": True,
                "user": user,
                "already_verified": user.is_verified,
                "expired": False,
            }
        
        # Se non trovato, cerca se il token esiste ma è scaduto
        doc_expired = await self.users_collection.find_one({
            "verification_token": token,
        })
        
        if doc_expired:
            user = self._doc_to_user(doc_expired)
            return {
                "valid": False,
                "user": user,
                "already_verified": user.is_verified,
                "expired": True,
            }
        
        # Se il token non esiste, potrebbe essere che l'utente sia già verificato
        # Cerca tutti gli utenti non verificati per vedere se qualcuno ha questo token
        # (ma questo è poco probabile, quindi restituiamo None)
        return None
    
    async def verify_email(self, token: str) -> Optional[User]:
        """
        Verifica email con token e attiva l'utente.
        
        Returns:
            User se token valido, None altrimenti
        """
        # Auto-connect se non connesso
        if self.users_collection is None:
            await self.connect()
        # Trova utente con token valido
        doc = await self.users_collection.find_one({
            "verification_token": token,
            "verification_expires": {"$gt": datetime.utcnow()}
        })
        
        if not doc:
            return None
        
        # Aggiorna utente come verificato
        await self.users_collection.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "is_verified": True,
                    "verification_token": None,
                    "verification_expires": None,
                    "updated_at": datetime.utcnow(),
                }
            }
        )
        
        # Restituisci utente aggiornato
        user = self._doc_to_user(doc)
        user.is_verified = True
        return user
    
    async def get_user_by_verification_token(self, token: str) -> Optional[User]:
        """Recupera utente per token di verifica (anche scaduto, per reinvio)."""
        # Auto-connect se non connesso
        if self.users_collection is None:
            await self.connect()
        doc = await self.users_collection.find_one({"verification_token": token})
        if doc:
            return self._doc_to_user(doc)
        return None


# Istanza globale
_user_store: Optional[UserStore] = None


def get_user_store() -> UserStore:
    """Restituisce l'istanza globale del UserStore."""
    global _user_store
    if _user_store is None:
        mongo_uri = os.getenv("MONGODB_URI")
        if not mongo_uri:
            raise ValueError("MONGODB_URI non configurato")
        _user_store = UserStore(mongo_uri)
    return _user_store
