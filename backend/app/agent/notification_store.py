"""Store MongoDB per notifiche."""
import os
import sys
from typing import Optional, Dict, Any, List
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING, DESCENDING
from app.models import Notification


class NotificationStore:
    """Store MongoDB per gestione notifiche."""
    
    def __init__(self, connection_string: str, database: str = "narrai", collection: str = "notifications"):
        """
        Inizializza il MongoDB notification store.
        
        Args:
            connection_string: MongoDB connection string
            database: Nome del database (default: "narrai")
            collection: Nome della collection (default: "notifications")
        """
        self.client: Optional[AsyncIOMotorClient] = None
        self.connection_string = connection_string
        self.database_name = database
        self.collection_name = collection
        self.db = None
        self.notifications_collection = None
        print(f"[NotificationStore] Inizializzato. DB: {database}, Collection: {collection}", file=sys.stderr)
    
    async def connect(self):
        """Connette al database MongoDB e crea gli indici."""
        if self.client is None:
            try:
                self.client = AsyncIOMotorClient(self.connection_string)
                self.db = self.client[self.database_name]
                self.notifications_collection = self.db[self.collection_name]
                
                # Crea indici per performance
                await self._create_indexes()
                
                print(f"[NotificationStore] Connesso a MongoDB: {self.database_name}", file=sys.stderr)
            except Exception as e:
                print(f"[NotificationStore] ERRORE nella connessione a MongoDB: {e}", file=sys.stderr)
                raise
    
    async def disconnect(self):
        """Chiude la connessione a MongoDB."""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            self.notifications_collection = None
            print(f"[NotificationStore] Disconnesso da MongoDB", file=sys.stderr)
    
    async def _create_indexes(self):
        """Crea indici per ottimizzare le query."""
        try:
            indexes = [
                IndexModel([("user_id", ASCENDING)]),
                IndexModel([("created_at", DESCENDING)]),
                IndexModel([("is_read", ASCENDING)]),
                IndexModel([("user_id", ASCENDING), ("is_read", ASCENDING)]),  # Compound index per query frequenti
            ]
            await self.notifications_collection.create_indexes(indexes)
            print(f"[NotificationStore] Indici creati con successo", file=sys.stderr)
        except Exception as e:
            print(f"[NotificationStore] Avviso: errore nella creazione indici: {e}", file=sys.stderr)
    
    def _notification_to_doc(self, notification: Notification) -> Dict[str, Any]:
        """Converte Notification in documento MongoDB."""
        doc = {
            "_id": notification.id,
            "user_id": notification.user_id,
            "type": notification.type,
            "title": notification.title,
            "message": notification.message,
            "data": notification.data,
            "is_read": notification.is_read,
            "created_at": notification.created_at,
        }
        return doc
    
    @classmethod
    def _doc_to_notification(cls, doc: Dict[str, Any]) -> Notification:
        """Converte documento MongoDB in Notification."""
        return Notification(
            id=doc["_id"],
            user_id=doc["user_id"],
            type=doc["type"],
            title=doc["title"],
            message=doc["message"],
            data=doc.get("data"),
            is_read=doc.get("is_read", False),
            created_at=doc.get("created_at", datetime.utcnow()),
        )
    
    async def create_notification(
        self,
        user_id: str,
        type: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        """
        Crea una nuova notifica.
        
        Args:
            user_id: ID del destinatario
            type: Tipo di notifica (connection_request, connection_accepted, book_shared, etc.)
            title: Titolo della notifica
            message: Messaggio della notifica
            data: Dati aggiuntivi (opzionale)
        
        Returns:
            Notification creata
        """
        import uuid
        notification_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        notification = Notification(
            id=notification_id,
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            data=data,
            is_read=False,
            created_at=now,
        )
        
        doc = self._notification_to_doc(notification)
        
        try:
            if self.notifications_collection is None:
                await self.connect()
            
            await self.notifications_collection.insert_one(doc)
            print(f"[NotificationStore] Notifica creata: {notification_id} per utente {user_id}", file=sys.stderr)
            return notification
        except Exception as e:
            print(f"[NotificationStore] ERRORE nella creazione notifica: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            raise
    
    async def get_notifications(
        self,
        user_id: str,
        limit: int = 50,
        skip: int = 0,
        unread_only: bool = False,
    ) -> List[Notification]:
        """
        Recupera notifiche per un utente.
        
        Args:
            user_id: ID utente
            limit: Numero massimo di notifiche da restituire
            skip: Numero di notifiche da saltare (per paginazione)
            unread_only: Se True, restituisce solo notifiche non lette
        
        Returns:
            Lista di notifiche ordinate per created_at (più recenti prima)
        """
        if self.notifications_collection is None:
            await self.connect()
        
        query = {"user_id": user_id}
        if unread_only:
            query["is_read"] = False
        
        try:
            cursor = self.notifications_collection.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
            notifications = []
            async for doc in cursor:
                notifications.append(self._doc_to_notification(doc))
            return notifications
        except Exception as e:
            print(f"[NotificationStore] ERRORE nel recupero notifiche: {e}", file=sys.stderr)
            raise
    
    async def get_unread_count(self, user_id: str) -> int:
        """
        Conta le notifiche non lette per un utente.
        
        Args:
            user_id: ID utente
        
        Returns:
            Numero di notifiche non lette
        """
        if self.notifications_collection is None:
            await self.connect()
        
        try:
            count = await self.notifications_collection.count_documents({
                "user_id": user_id,
                "is_read": False
            })
            return count
        except Exception as e:
            print(f"[NotificationStore] ERRORE nel conteggio notifiche non lette: {e}", file=sys.stderr)
            raise
    
    async def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """
        Marca una notifica come letta.
        
        Args:
            notification_id: ID della notifica
            user_id: ID utente (per verificare ownership)
        
        Returns:
            True se aggiornata con successo, False altrimenti
        """
        if self.notifications_collection is None:
            await self.connect()
        
        try:
            result = await self.notifications_collection.update_one(
                {"_id": notification_id, "user_id": user_id},
                {"$set": {"is_read": True}}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"[NotificationStore] ERRORE nel marcare notifica come letta: {e}", file=sys.stderr)
            raise
    
    async def mark_all_as_read(self, user_id: str) -> int:
        """
        Marca tutte le notifiche di un utente come lette.
        
        Args:
            user_id: ID utente
        
        Returns:
            Numero di notifiche aggiornate
        """
        if self.notifications_collection is None:
            await self.connect()
        
        try:
            result = await self.notifications_collection.update_many(
                {"user_id": user_id, "is_read": False},
                {"$set": {"is_read": True}}
            )
            return result.modified_count
        except Exception as e:
            print(f"[NotificationStore] ERRORE nel marcare tutte le notifiche come lette: {e}", file=sys.stderr)
            raise
    
    async def delete_notification(self, notification_id: str, user_id: str) -> bool:
        """
        Elimina una notifica.
        
        Args:
            notification_id: ID della notifica
            user_id: ID utente (per verificare ownership)
        
        Returns:
            True se eliminata con successo, False altrimenti
        """
        if self.notifications_collection is None:
            await self.connect()
        
        try:
            result = await self.notifications_collection.delete_one({
                "_id": notification_id,
                "user_id": user_id
            })
            return result.deleted_count > 0
        except Exception as e:
            print(f"[NotificationStore] ERRORE nell'eliminazione notifica: {e}", file=sys.stderr)
            raise

    async def get_user_notifications(self, user_id: str, limit: int = 100) -> list:
        """
        Recupera tutte le notifiche di un utente (per export GDPR).
        
        Args:
            user_id: ID utente
            limit: Numero massimo di notifiche
        
        Returns:
            Lista di notifiche
        """
        if self.notifications_collection is None:
            await self.connect()
        
        try:
            from app.models import Notification
            cursor = self.notifications_collection.find(
                {"user_id": user_id}
            ).sort("created_at", -1).limit(limit)
            
            notifications = []
            async for doc in cursor:
                notifications.append(Notification(
                    id=doc["_id"],
                    user_id=doc["user_id"],
                    type=doc["type"],
                    title=doc["title"],
                    message=doc["message"],
                    data=doc.get("data"),
                    is_read=doc.get("is_read", False),
                    created_at=doc["created_at"]
                ))
            return notifications
        except Exception as e:
            print(f"[NotificationStore] ERRORE get_user_notifications: {e}", file=sys.stderr)
            return []

    async def delete_user_notifications(self, user_id: str) -> int:
        """
        Elimina tutte le notifiche di un utente (per cancellazione account GDPR).
        
        Args:
            user_id: ID utente
        
        Returns:
            Numero di notifiche eliminate
        """
        if self.notifications_collection is None:
            await self.connect()
        
        try:
            result = await self.notifications_collection.delete_many({"user_id": user_id})
            print(f"[NotificationStore] Eliminate {result.deleted_count} notifiche per utente {user_id}", file=sys.stderr)
            return result.deleted_count
        except Exception as e:
            print(f"[NotificationStore] ERRORE delete_user_notifications: {e}", file=sys.stderr)
            return 0

    async def count_user_notifications(self, user_id: str) -> int:
        """
        Conta le notifiche di un utente.
        
        Args:
            user_id: ID utente
        
        Returns:
            Numero di notifiche
        """
        if self.notifications_collection is None:
            await self.connect()
        
        try:
            count = await self.notifications_collection.count_documents({"user_id": user_id})
            return count
        except Exception as e:
            print(f"[NotificationStore] ERRORE count_user_notifications: {e}", file=sys.stderr)
            return 0


# Istanza globale
_notification_store: Optional[NotificationStore] = None


def get_notification_store() -> NotificationStore:
    """Restituisce l'istanza globale del NotificationStore."""
    global _notification_store
    if _notification_store is None:
        mongo_uri = os.getenv("MONGODB_URI")
        if not mongo_uri:
            raise ValueError("MONGODB_URI non configurato")
        _notification_store = NotificationStore(mongo_uri)
    return _notification_store
