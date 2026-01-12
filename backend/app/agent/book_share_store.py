"""Store MongoDB per condivisioni di libri."""
import os
import sys
from typing import Optional, Dict, Any, List
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from app.models import BookShare


class BookShareStore:
    """Store MongoDB per gestione condivisioni di libri."""
    
    def __init__(self, connection_string: str, database: str = "narrai", collection: str = "book_shares"):
        """
        Inizializza il MongoDB book share store.
        
        Args:
            connection_string: MongoDB connection string
            database: Nome del database (default: "narrai")
            collection: Nome della collection (default: "book_shares")
        """
        self.client: Optional[AsyncIOMotorClient] = None
        self.connection_string = connection_string
        self.database_name = database
        self.collection_name = collection
        self.db = None
        self.shares_collection = None
        print(f"[BookShareStore] Inizializzato. DB: {database}, Collection: {collection}", file=sys.stderr)
    
    async def connect(self):
        """Connette al database MongoDB e crea gli indici."""
        if self.client is None:
            try:
                self.client = AsyncIOMotorClient(self.connection_string)
                self.db = self.client[self.database_name]
                self.shares_collection = self.db[self.collection_name]
                
                # Crea indici per performance
                await self._create_indexes()
                
                print(f"[BookShareStore] Connesso a MongoDB: {self.database_name}", file=sys.stderr)
            except Exception as e:
                print(f"[BookShareStore] ERRORE nella connessione a MongoDB: {e}", file=sys.stderr)
                raise
    
    async def disconnect(self):
        """Chiude la connessione a MongoDB."""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            self.shares_collection = None
            print(f"[BookShareStore] Disconnesso da MongoDB", file=sys.stderr)
    
    async def _create_indexes(self):
        """Crea indici per ottimizzare le query."""
        try:
            indexes = [
                IndexModel([("book_session_id", ASCENDING)]),
                IndexModel([("owner_id", ASCENDING)]),
                IndexModel([("recipient_id", ASCENDING)]),
                IndexModel([("status", ASCENDING)]),
                IndexModel([("created_at", DESCENDING)]),
                # Compound index unique per evitare condivisioni duplicate
                IndexModel([("book_session_id", ASCENDING), ("recipient_id", ASCENDING)], unique=True),
                # Compound index per query frequenti (owner + recipient + status)
                IndexModel([("owner_id", ASCENDING), ("recipient_id", ASCENDING), ("status", ASCENDING)]),
            ]
            await self.shares_collection.create_indexes(indexes)
            print(f"[BookShareStore] Indici creati con successo", file=sys.stderr)
        except Exception as e:
            print(f"[BookShareStore] Avviso: errore nella creazione indici: {e}", file=sys.stderr)
    
    def _share_to_doc(self, share: BookShare) -> Dict[str, Any]:
        """Converte BookShare in documento MongoDB."""
        doc = {
            "_id": share.id,
            "book_session_id": share.book_session_id,
            "owner_id": share.owner_id,
            "recipient_id": share.recipient_id,
            "status": share.status,
            "created_at": share.created_at,
            "updated_at": share.updated_at,
        }
        return doc
    
    @classmethod
    def _doc_to_share(cls, doc: Dict[str, Any]) -> BookShare:
        """Converte documento MongoDB in BookShare."""
        return BookShare(
            id=doc["_id"],
            book_session_id=doc["book_session_id"],
            owner_id=doc["owner_id"],
            recipient_id=doc["recipient_id"],
            status=doc["status"],
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
            owner_name=doc.get("owner_name"),
            recipient_name=doc.get("recipient_name"),
            book_title=doc.get("book_title"),
        )
    
    async def create_book_share(
        self,
        book_session_id: str,
        owner_id: str,
        recipient_id: str,
        status: str = "pending",
    ) -> BookShare:
        """
        Crea una nuova condivisione di libro.
        
        Args:
            book_session_id: ID sessione del libro
            owner_id: ID utente proprietario
            recipient_id: ID utente destinatario
            status: Stato della condivisione (default: "pending")
        
        Returns:
            BookShare creata
        
        Raises:
            ValueError: Se condivisione già esistente
        """
        import uuid
        share_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        share = BookShare(
            id=share_id,
            book_session_id=book_session_id,
            owner_id=owner_id,
            recipient_id=recipient_id,
            status=status,
            created_at=now,
            updated_at=now,
        )
        
        doc = self._share_to_doc(share)
        
        try:
            if self.shares_collection is None:
                await self.connect()
            
            await self.shares_collection.insert_one(doc)
            print(f"[BookShareStore] Condivisione creata: {share_id} (book: {book_session_id}, {owner_id} -> {recipient_id}, {status})", file=sys.stderr)
            return share
        except DuplicateKeyError:
            print(f"[BookShareStore] Condivisione già esistente: {book_session_id} -> {recipient_id}", file=sys.stderr)
            raise ValueError(f"Libro già condiviso con questo utente")
        except Exception as e:
            print(f"[BookShareStore] ERRORE nella creazione condivisione: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            raise
    
    async def get_book_share(
        self,
        book_session_id: str,
        recipient_id: str,
    ) -> Optional[BookShare]:
        """
        Recupera una condivisione specifica di un libro.
        
        Args:
            book_session_id: ID sessione del libro
            recipient_id: ID utente destinatario
        
        Returns:
            BookShare se trovata, None altrimenti
        """
        if self.shares_collection is None:
            await self.connect()
        
        try:
            doc = await self.shares_collection.find_one({
                "book_session_id": book_session_id,
                "recipient_id": recipient_id
            })
            
            if doc:
                return self._doc_to_share(doc)
            return None
        except Exception as e:
            print(f"[BookShareStore] ERRORE nel recupero condivisione: {e}", file=sys.stderr)
            raise
    
    async def check_share_exists(
        self,
        book_session_id: str,
        owner_id: str,
        recipient_id: str,
    ) -> bool:
        """
        Verifica se esiste una condivisione tra owner e recipient per un libro.
        
        Args:
            book_session_id: ID sessione del libro
            owner_id: ID utente proprietario
            recipient_id: ID utente destinatario
        
        Returns:
            True se esiste, False altrimenti
        """
        share = await self.get_book_share(book_session_id, recipient_id)
        if share and share.owner_id == owner_id:
            return True
        return False
    
    async def get_shares_by_book(self, book_session_id: str) -> List[BookShare]:
        """
        Recupera tutte le condivisioni attive (accepted) per un libro.
        
        Args:
            book_session_id: ID sessione del libro
        
        Returns:
            Lista di condivisioni attive per il libro
        """
        if self.shares_collection is None:
            await self.connect()
        
        try:
            cursor = self.shares_collection.find({
                "book_session_id": book_session_id,
                "status": "accepted"
            })
            shares = []
            async for doc in cursor:
                shares.append(self._doc_to_share(doc))
            return shares
        except Exception as e:
            print(f"[BookShareStore] ERRORE nel recupero condivisioni per libro {book_session_id}: {e}", file=sys.stderr)
            return []
    
    async def get_user_shared_books(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[BookShare]:
        """
        Recupera i libri condivisi con l'utente (come destinatario).
        
        Args:
            user_id: ID utente destinatario
            status: Filtra per status (opzionale)
            limit: Numero massimo di risultati
            skip: Numero di risultati da saltare
        
        Returns:
            Lista di condivisioni ordinate per created_at (più recenti prima)
        """
        if self.shares_collection is None:
            await self.connect()
        
        query = {"recipient_id": user_id}
        
        if status:
            query["status"] = status
        
        try:
            cursor = self.shares_collection.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
            shares = []
            async for doc in cursor:
                shares.append(self._doc_to_share(doc))
            return shares
        except Exception as e:
            print(f"[BookShareStore] ERRORE nel recupero libri condivisi: {e}", file=sys.stderr)
            raise
    
    async def get_user_shared_to_others(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[BookShare]:
        """
        Recupera i libri che l'utente ha condiviso con altri (come owner).
        
        Args:
            user_id: ID utente proprietario
            status: Filtra per status (opzionale)
            limit: Numero massimo di risultati
            skip: Numero di risultati da saltare
        
        Returns:
            Lista di condivisioni ordinate per created_at (più recenti prima)
        """
        if self.shares_collection is None:
            await self.connect()
        
        query = {"owner_id": user_id}
        
        if status:
            query["status"] = status
        
        try:
            cursor = self.shares_collection.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
            shares = []
            async for doc in cursor:
                shares.append(self._doc_to_share(doc))
            return shares
        except Exception as e:
            print(f"[BookShareStore] ERRORE nel recupero libri condivisi con altri: {e}", file=sys.stderr)
            raise
    
    async def update_share_status(
        self,
        share_id: str,
        status: str,
        user_id: str,  # Per verificare ownership
    ) -> Optional[BookShare]:
        """
        Aggiorna lo stato di una condivisione.
        
        Args:
            share_id: ID della condivisione
            status: Nuovo stato (pending, accepted, declined)
            user_id: ID utente che esegue l'azione (per verificare ownership)
        
        Returns:
            BookShare aggiornata se trovata e ownership verificata, None altrimenti
        """
        if self.shares_collection is None:
            await self.connect()
        
        try:
            # Verifica che la condivisione esista e che l'utente sia autorizzato
            doc = await self.shares_collection.find_one({"_id": share_id})
            if not doc:
                return None
            
            share = self._doc_to_share(doc)
            
            # Verifica ownership: per accettare/rifiutare, l'utente deve essere il destinatario
            if status in ["accepted", "declined"]:
                if share.recipient_id != user_id:
                    print(f"[BookShareStore] ERRORE: Utente {user_id} non autorizzato ad accettare/rifiutare condivisione {share_id}", file=sys.stderr)
                    return None
            
            # Aggiorna
            result = await self.shares_collection.update_one(
                {"_id": share_id},
                {
                    "$set": {
                        "status": status,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                share.status = status
                share.updated_at = datetime.utcnow()
                print(f"[BookShareStore] Condivisione {share_id} aggiornata a status: {status}", file=sys.stderr)
                return share
            
            return None
        except Exception as e:
            print(f"[BookShareStore] ERRORE nell'aggiornamento condivisione: {e}", file=sys.stderr)
            raise
    
    async def resend_share(
        self,
        book_session_id: str,
        owner_id: str,
        recipient_id: str,
    ) -> Optional[BookShare]:
        """
        Ri-condivide un libro esistente (resetta a pending).
        Solo l'owner può ri-condividere.
        
        Args:
            book_session_id: ID sessione del libro
            owner_id: ID utente proprietario
            recipient_id: ID utente destinatario
        
        Returns:
            BookShare aggiornata se trovata e ownership verificata, None altrimenti
        """
        if self.shares_collection is None:
            await self.connect()
        
        try:
            # Recupera la condivisione esistente
            doc = await self.shares_collection.find_one({
                "book_session_id": book_session_id,
                "recipient_id": recipient_id
            })
            
            if not doc:
                return None
            
            share = self._doc_to_share(doc)
            
            # Verifica che l'utente sia l'owner
            if share.owner_id != owner_id:
                print(f"[BookShareStore] ERRORE: Utente {owner_id} non è l'owner della condivisione", file=sys.stderr)
                return None
            
            # Non permettere di ri-condividere se già accettata
            if share.status == "accepted":
                return None
            
            # Aggiorna a pending
            result = await self.shares_collection.update_one(
                {"_id": share.id},
                {
                    "$set": {
                        "status": "pending",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                share.status = "pending"
                share.updated_at = datetime.utcnow()
                print(f"[BookShareStore] Condivisione {share.id} ri-inviata (resettata a pending) da owner {owner_id}", file=sys.stderr)
                return share
            
            return None
        except Exception as e:
            print(f"[BookShareStore] ERRORE nel ri-invio condivisione: {e}", file=sys.stderr)
            raise
    
    async def delete_book_share(
        self,
        share_id: str,
        user_id: str,  # Per verificare ownership
    ) -> bool:
        """
        Elimina una condivisione (revoca accesso).
        
        Args:
            share_id: ID della condivisione
            user_id: ID utente che esegue l'azione (per verificare ownership - deve essere owner)
        
        Returns:
            True se eliminata con successo, False altrimenti
        """
        if self.shares_collection is None:
            await self.connect()
        
        try:
            # Verifica ownership: l'utente deve essere l'owner
            doc = await self.shares_collection.find_one({"_id": share_id})
            if not doc:
                return False
            
            share = self._doc_to_share(doc)
            
            # Verifica che l'utente sia l'owner
            if share.owner_id != user_id:
                print(f"[BookShareStore] ERRORE: Utente {user_id} non autorizzato ad eliminare condivisione {share_id}", file=sys.stderr)
                return False
            
            # Elimina
            result = await self.shares_collection.delete_one({"_id": share_id})
            deleted = result.deleted_count > 0
            
            if deleted:
                print(f"[BookShareStore] Condivisione {share_id} eliminata da {user_id}", file=sys.stderr)
            
            return deleted
        except Exception as e:
            print(f"[BookShareStore] ERRORE nell'eliminazione condivisione: {e}", file=sys.stderr)
            raise
    
    async def get_all_shares_for_book(
        self,
        book_session_id: str,
        owner_id: str,  # Per verificare ownership
    ) -> List[BookShare]:
        """
        Recupera tutte le condivisioni di un libro specifico (solo per owner).
        
        Args:
            book_session_id: ID sessione del libro
            owner_id: ID utente proprietario (per verificare ownership)
        
        Returns:
            Lista di condivisioni ordinate per created_at (più recenti prima)
        """
        if self.shares_collection is None:
            await self.connect()
        
        query = {
            "book_session_id": book_session_id,
            "owner_id": owner_id
        }
        
        try:
            cursor = self.shares_collection.find(query).sort("created_at", DESCENDING)
            shares = []
            async for doc in cursor:
                shares.append(self._doc_to_share(doc))
            return shares
        except Exception as e:
            print(f"[BookShareStore] ERRORE nel recupero condivisioni libro: {e}", file=sys.stderr)
            raise
    
    async def check_user_has_access(
        self,
        book_session_id: str,
        user_id: str,
        owner_id: str,
    ) -> bool:
        """
        Verifica se un utente ha accesso a un libro (owner o condivisione accettata).
        
        Args:
            book_session_id: ID sessione del libro
            user_id: ID utente da verificare
            owner_id: ID utente proprietario
        
        Returns:
            True se l'utente è owner o ha condivisione accettata, False altrimenti
        """
        # Se è l'owner, ha sempre accesso
        if user_id == owner_id:
            return True
        
        # Verifica se esiste condivisione accettata
        share = await self.get_book_share(book_session_id, user_id)
        if share and share.status == "accepted":
            return True
        
        return False
    
    async def delete_all_shares_for_book(
        self,
        book_session_id: str,
        owner_id: str,
    ) -> int:
        """
        Elimina tutte le condivisioni di un libro (utile quando si elimina il libro).
        
        Args:
            book_session_id: ID sessione del libro
            owner_id: ID utente proprietario
        
        Returns:
            Numero di condivisioni eliminate
        """
        if self.shares_collection is None:
            await self.connect()
        
        try:
            result = await self.shares_collection.delete_many({
                "book_session_id": book_session_id,
                "owner_id": owner_id
            })
            deleted_count = result.deleted_count
            if deleted_count > 0:
                print(f"[BookShareStore] Eliminate {deleted_count} condivisioni per libro {book_session_id}", file=sys.stderr)
            return deleted_count
        except Exception as e:
            print(f"[BookShareStore] ERRORE nell'eliminazione condivisioni libro: {e}", file=sys.stderr)
            raise


# Istanza globale
_book_share_store: Optional[BookShareStore] = None


def get_book_share_store() -> BookShareStore:
    """Restituisce l'istanza globale del BookShareStore."""
    global _book_share_store
    if _book_share_store is None:
        mongo_uri = os.getenv("MONGODB_URI")
        if not mongo_uri:
            raise ValueError("MONGODB_URI non configurato")
        _book_share_store = BookShareStore(mongo_uri)
    return _book_share_store
