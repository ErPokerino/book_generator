"""Store MongoDB per connessioni tra utenti."""
import os
import sys
from typing import Optional, Dict, Any, List
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from app.models import Connection


class ConnectionStore:
    """Store MongoDB per gestione connessioni tra utenti."""
    
    def __init__(self, connection_string: str, database: str = "narrai", collection: str = "connections"):
        """
        Inizializza il MongoDB connection store.
        
        Args:
            connection_string: MongoDB connection string
            database: Nome del database (default: "narrai")
            collection: Nome della collection (default: "connections")
        """
        self.client: Optional[AsyncIOMotorClient] = None
        self.connection_string = connection_string
        self.database_name = database
        self.collection_name = collection
        self.db = None
        self.connections_collection = None
        print(f"[ConnectionStore] Inizializzato. DB: {database}, Collection: {collection}", file=sys.stderr)
    
    async def connect(self):
        """Connette al database MongoDB e crea gli indici."""
        if self.client is None:
            try:
                self.client = AsyncIOMotorClient(self.connection_string)
                self.db = self.client[self.database_name]
                self.connections_collection = self.db[self.collection_name]
                
                # Crea indici per performance
                await self._create_indexes()
                
                print(f"[ConnectionStore] Connesso a MongoDB: {self.database_name}", file=sys.stderr)
            except Exception as e:
                print(f"[ConnectionStore] ERRORE nella connessione a MongoDB: {e}", file=sys.stderr)
                raise
    
    async def disconnect(self):
        """Chiude la connessione a MongoDB."""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            self.connections_collection = None
            print(f"[ConnectionStore] Disconnesso da MongoDB", file=sys.stderr)
    
    async def _create_indexes(self):
        """Crea indici per ottimizzare le query."""
        try:
            indexes = [
                IndexModel([("from_user_id", ASCENDING)]),
                IndexModel([("to_user_id", ASCENDING)]),
                IndexModel([("status", ASCENDING)]),
                IndexModel([("created_at", DESCENDING)]),
                # Compound index unique per evitare connessioni duplicate
                IndexModel([("from_user_id", ASCENDING), ("to_user_id", ASCENDING)], unique=True),
            ]
            await self.connections_collection.create_indexes(indexes)
            print(f"[ConnectionStore] Indici creati con successo", file=sys.stderr)
        except Exception as e:
            print(f"[ConnectionStore] Avviso: errore nella creazione indici: {e}", file=sys.stderr)
    
    def _connection_to_doc(self, connection: Connection) -> Dict[str, Any]:
        """Converte Connection in documento MongoDB."""
        doc = {
            "_id": connection.id,
            "from_user_id": connection.from_user_id,
            "to_user_id": connection.to_user_id,
            "status": connection.status,
            "created_at": connection.created_at,
            "updated_at": connection.updated_at,
        }
        return doc
    
    @classmethod
    def _doc_to_connection(cls, doc: Dict[str, Any]) -> Connection:
        """Converte documento MongoDB in Connection."""
        return Connection(
            id=doc["_id"],
            from_user_id=doc["from_user_id"],
            to_user_id=doc["to_user_id"],
            status=doc["status"],
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )
    
    async def create_connection(
        self,
        from_user_id: str,
        to_user_id: str,
        status: str = "pending",
    ) -> Connection:
        """
        Crea una nuova connessione.
        
        Args:
            from_user_id: ID utente che invia la richiesta
            to_user_id: ID utente che riceve la richiesta
            status: Stato della connessione (default: "pending")
        
        Returns:
            Connection creata
        
        Raises:
            ValueError: Se connessione già esistente
        """
        import uuid
        connection_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        connection = Connection(
            id=connection_id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            status=status,
            created_at=now,
            updated_at=now,
        )
        
        doc = self._connection_to_doc(connection)
        
        try:
            if self.connections_collection is None:
                await self.connect()
            
            await self.connections_collection.insert_one(doc)
            print(f"[ConnectionStore] Connessione creata: {connection_id} ({from_user_id} -> {to_user_id}, {status})", file=sys.stderr)
            return connection
        except DuplicateKeyError:
            print(f"[ConnectionStore] Connessione già esistente: {from_user_id} -> {to_user_id}", file=sys.stderr)
            raise ValueError(f"Connessione già esistente tra questi utenti")
        except Exception as e:
            print(f"[ConnectionStore] ERRORE nella creazione connessione: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            raise
    
    async def get_connection(
        self,
        from_user_id: str,
        to_user_id: str,
    ) -> Optional[Connection]:
        """
        Recupera una connessione tra due utenti (in qualsiasi direzione).
        
        Args:
            from_user_id: ID primo utente
            to_user_id: ID secondo utente
        
        Returns:
            Connection se trovata, None altrimenti
        """
        if self.connections_collection is None:
            await self.connect()
        
        try:
            # Cerca in entrambe le direzioni
            doc = await self.connections_collection.find_one({
                "$or": [
                    {"from_user_id": from_user_id, "to_user_id": to_user_id},
                    {"from_user_id": to_user_id, "to_user_id": from_user_id}
                ]
            })
            
            if doc:
                return self._doc_to_connection(doc)
            return None
        except Exception as e:
            print(f"[ConnectionStore] ERRORE nel recupero connessione: {e}", file=sys.stderr)
            raise
    
    async def check_connection_exists(
        self,
        from_user_id: str,
        to_user_id: str,
    ) -> bool:
        """
        Verifica se esiste una connessione tra due utenti.
        
        Args:
            from_user_id: ID primo utente
            to_user_id: ID secondo utente
        
        Returns:
            True se esiste, False altrimenti
        """
        connection = await self.get_connection(from_user_id, to_user_id)
        return connection is not None
    
    async def get_user_connections(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Connection]:
        """
        Recupera tutte le connessioni di un utente (sia come mittente che destinatario).
        
        Args:
            user_id: ID utente
            status: Filtra per status (opzionale)
            limit: Numero massimo di risultati
            skip: Numero di risultati da saltare
        
        Returns:
            Lista di connessioni ordinate per created_at (più recenti prima)
        """
        if self.connections_collection is None:
            await self.connect()
        
        query = {
            "$or": [
                {"from_user_id": user_id},
                {"to_user_id": user_id}
            ]
        }
        
        if status:
            query["status"] = status
        
        try:
            cursor = self.connections_collection.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
            connections = []
            async for doc in cursor:
                connections.append(self._doc_to_connection(doc))
            return connections
        except Exception as e:
            print(f"[ConnectionStore] ERRORE nel recupero connessioni utente: {e}", file=sys.stderr)
            raise
    
    async def get_pending_requests(
        self,
        user_id: str,
        incoming_only: bool = False,
    ) -> List[Connection]:
        """
        Recupera le richieste pendenti per un utente.
        
        Args:
            user_id: ID utente
            incoming_only: Se True, solo richieste in arrivo (to_user_id = user_id)
                         Se False, anche richieste in uscita (from_user_id = user_id)
        
        Returns:
            Lista di connessioni PENDING
        """
        if self.connections_collection is None:
            await self.connect()
        
        if incoming_only:
            query = {
                "to_user_id": user_id,
                "status": "pending"
            }
        else:
            query = {
                "$or": [
                    {"from_user_id": user_id, "status": "pending"},
                    {"to_user_id": user_id, "status": "pending"}
                ]
            }
        
        try:
            cursor = self.connections_collection.find(query).sort("created_at", DESCENDING)
            connections = []
            async for doc in cursor:
                connections.append(self._doc_to_connection(doc))
            return connections
        except Exception as e:
            print(f"[ConnectionStore] ERRORE nel recupero richieste pendenti: {e}", file=sys.stderr)
            raise
    
    async def update_connection_status(
        self,
        connection_id: str,
        status: str,
        user_id: str,  # Per verificare ownership
    ) -> Optional[Connection]:
        """
        Aggiorna lo stato di una connessione.
        
        Args:
            connection_id: ID della connessione
            status: Nuovo stato (pending, accepted)
            user_id: ID utente che esegue l'azione (per verificare ownership)
        
        Returns:
            Connection aggiornata se trovata e ownership verificata, None altrimenti
        """
        if self.connections_collection is None:
            await self.connect()
        
        try:
            # Verifica che la connessione esista e che l'utente sia autorizzato
            doc = await self.connections_collection.find_one({"_id": connection_id})
            if not doc:
                return None
            
            connection = self._doc_to_connection(doc)
            
            # Verifica ownership: l'utente deve essere il destinatario (to_user_id) per accettare
            # o il mittente (from_user_id) per altre azioni
            if status == "accepted":
                if connection.to_user_id != user_id:
                    print(f"[ConnectionStore] ERRORE: Utente {user_id} non autorizzato ad accettare connessione {connection_id}", file=sys.stderr)
                    return None
            
            # Aggiorna
            result = await self.connections_collection.update_one(
                {"_id": connection_id},
                {
                    "$set": {
                        "status": status,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                connection.status = status
                connection.updated_at = datetime.utcnow()
                print(f"[ConnectionStore] Connessione {connection_id} aggiornata a status: {status}", file=sys.stderr)
                return connection
            
            return None
        except Exception as e:
            print(f"[ConnectionStore] ERRORE nell'aggiornamento connessione: {e}", file=sys.stderr)
            raise
    
    async def delete_connection(
        self,
        connection_id: str,
        user_id: str,  # Per verificare ownership
    ) -> bool:
        """
        Elimina una connessione.
        
        Args:
            connection_id: ID della connessione
            user_id: ID utente che esegue l'azione (per verificare ownership)
        
        Returns:
            True se eliminata con successo, False altrimenti
        """
        if self.connections_collection is None:
            await self.connect()
        
        try:
            # Verifica ownership: l'utente deve essere parte della connessione
            doc = await self.connections_collection.find_one({"_id": connection_id})
            if not doc:
                return False
            
            connection = self._doc_to_connection(doc)
            
            # Verifica che l'utente sia parte della connessione
            if connection.from_user_id != user_id and connection.to_user_id != user_id:
                print(f"[ConnectionStore] ERRORE: Utente {user_id} non autorizzato ad eliminare connessione {connection_id}", file=sys.stderr)
                return False
            
            # Elimina
            result = await self.connections_collection.delete_one({"_id": connection_id})
            deleted = result.deleted_count > 0
            
            if deleted:
                print(f"[ConnectionStore] Connessione {connection_id} eliminata da {user_id}", file=sys.stderr)
            
            return deleted
        except Exception as e:
            print(f"[ConnectionStore] ERRORE nell'eliminazione connessione: {e}", file=sys.stderr)
            raise

    async def anonymize_user_connections(self, user_id: str) -> int:
        """
        Anonimizza le connessioni di un utente (per cancellazione account GDPR).
        Sostituisce i dati identificativi con placeholder.
        
        Args:
            user_id: ID utente da anonimizzare
        
        Returns:
            Numero di connessioni anonimizzate
        """
        if self.connections_collection is None:
            await self.connect()
        
        try:
            from datetime import datetime
            
            # Anonimizza connessioni dove l'utente e il mittente
            result_from = await self.connections_collection.update_many(
                {"from_user_id": user_id},
                {
                    "$set": {
                        "from_user_id": "[DELETED]",
                        "from_user_name": "[Utente eliminato]",
                        "from_user_email": "[deleted]",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            # Anonimizza connessioni dove l'utente e il destinatario
            result_to = await self.connections_collection.update_many(
                {"to_user_id": user_id},
                {
                    "$set": {
                        "to_user_id": "[DELETED]",
                        "to_user_name": "[Utente eliminato]",
                        "to_user_email": "[deleted]",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            total = result_from.modified_count + result_to.modified_count
            print(f"[ConnectionStore] Anonimizzate {total} connessioni per utente {user_id}", file=sys.stderr)
            return total
        except Exception as e:
            print(f"[ConnectionStore] ERRORE anonymize_user_connections: {e}", file=sys.stderr)
            return 0


# Istanza globale
_connection_store: Optional[ConnectionStore] = None


def get_connection_store() -> ConnectionStore:
    """Restituisce l'istanza globale del ConnectionStore."""
    global _connection_store
    if _connection_store is None:
        mongo_uri = os.getenv("MONGODB_URI")
        if not mongo_uri:
            raise ValueError("MONGODB_URI non configurato")
        _connection_store = ConnectionStore(mongo_uri)
    return _connection_store
