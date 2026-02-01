"""Store MongoDB per gestione crediti e transazioni."""
import os
import sys
from typing import Optional, List, Tuple
from datetime import datetime
import uuid
import yaml
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING, DESCENDING
from app.models import (
    CreditPackage, 
    CreditTransaction, 
    DEFAULT_CREDITS,
    MODE_COSTS
)


class CreditStore:
    """Store MongoDB per gestione crediti, transazioni e pacchetti."""
    
    def __init__(
        self, 
        connection_string: str, 
        database: str = "narrai", 
        transactions_collection: str = "credit_transactions",
        packages_collection: str = "credit_packages",
        users_collection: str = "users"
    ):
        """
        Inizializza il MongoDB credit store.
        
        Args:
            connection_string: MongoDB connection string
            database: Nome del database (default: "narrai")
            transactions_collection: Nome collection transazioni (default: "credit_transactions")
            packages_collection: Nome collection pacchetti (default: "credit_packages")
            users_collection: Nome collection utenti (default: "users")
        """
        self.client: Optional[AsyncIOMotorClient] = None
        self.connection_string = connection_string
        self.database_name = database
        self.transactions_collection_name = transactions_collection
        self.packages_collection_name = packages_collection
        self.users_collection_name = users_collection
        self.db = None
        self.transactions_collection = None
        self.packages_collection = None
        self.users_collection = None
        print(f"[CreditStore] Inizializzato. DB: {database}", file=sys.stderr)
    
    async def connect(self):
        """Connette al database MongoDB e crea gli indici."""
        if self.client is None:
            try:
                self.client = AsyncIOMotorClient(self.connection_string)
                self.db = self.client[self.database_name]
                self.transactions_collection = self.db[self.transactions_collection_name]
                self.packages_collection = self.db[self.packages_collection_name]
                self.users_collection = self.db[self.users_collection_name]
                
                # Crea indici per performance
                await self._create_indexes()
                
                print(f"[CreditStore] Connesso a MongoDB: {self.database_name}", file=sys.stderr)
            except Exception as e:
                print(f"[CreditStore] ERRORE nella connessione a MongoDB: {e}", file=sys.stderr)
                raise
    
    async def disconnect(self):
        """Chiude la connessione a MongoDB."""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            self.transactions_collection = None
            self.packages_collection = None
            self.users_collection = None
            print(f"[CreditStore] Disconnesso da MongoDB", file=sys.stderr)
    
    async def _create_indexes(self):
        """Crea indici per ottimizzare le query."""
        try:
            # Indici per transazioni
            tx_indexes = [
                IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)]),
                IndexModel([("type", ASCENDING)]),
                IndexModel([("created_at", DESCENDING)]),
            ]
            await self.transactions_collection.create_indexes(tx_indexes)
            
            # Indici per pacchetti
            pkg_indexes = [
                IndexModel([("is_active", ASCENDING)]),
                IndexModel([("sort_order", ASCENDING)]),
            ]
            await self.packages_collection.create_indexes(pkg_indexes)
            
            print(f"[CreditStore] Indici creati con successo", file=sys.stderr)
        except Exception as e:
            print(f"[CreditStore] Avviso: errore nella creazione indici: {e}", file=sys.stderr)
    
    # ==================== GESTIONE PACCHETTI ====================
    
    def _package_to_doc(self, package: CreditPackage) -> dict:
        """Converte CreditPackage in documento MongoDB."""
        return {
            "_id": package.id,
            "name": package.name,
            "credits": package.credits,
            "price_eur": package.price_eur,
            "bonus_credits": package.bonus_credits,
            "description": package.description,
            "is_active": package.is_active,
            "sort_order": package.sort_order,
            "icon": package.icon,
        }
    
    @classmethod
    def _doc_to_package(cls, doc: dict) -> CreditPackage:
        """Converte documento MongoDB in CreditPackage."""
        return CreditPackage(
            id=doc["_id"],
            name=doc["name"],
            credits=doc["credits"],
            price_eur=doc.get("price_eur", 0.0),
            bonus_credits=doc.get("bonus_credits", 0),
            description=doc.get("description"),
            is_active=doc.get("is_active", True),
            sort_order=doc.get("sort_order", 0),
            icon=doc.get("icon"),
        )
    
    async def get_active_packages(self) -> List[CreditPackage]:
        """
        Recupera tutti i pacchetti crediti attivi.
        
        Returns:
            Lista di CreditPackage ordinati per sort_order
        """
        if self.packages_collection is None:
            await self.connect()
        
        packages = []
        cursor = self.packages_collection.find({"is_active": True}).sort("sort_order", ASCENDING)
        async for doc in cursor:
            packages.append(self._doc_to_package(doc))
        
        return packages
    
    async def get_package_by_id(self, package_id: str) -> Optional[CreditPackage]:
        """
        Recupera un pacchetto per ID.
        
        Args:
            package_id: ID del pacchetto
        
        Returns:
            CreditPackage o None se non trovato
        """
        if self.packages_collection is None:
            await self.connect()
        
        doc = await self.packages_collection.find_one({"_id": package_id})
        if doc:
            return self._doc_to_package(doc)
        return None
    
    async def create_package(self, package: CreditPackage) -> CreditPackage:
        """
        Crea un nuovo pacchetto crediti.
        
        Args:
            package: CreditPackage da creare
        
        Returns:
            CreditPackage creato
        """
        if self.packages_collection is None:
            await self.connect()
        
        doc = self._package_to_doc(package)
        await self.packages_collection.insert_one(doc)
        print(f"[CreditStore] Pacchetto creato: {package.name}", file=sys.stderr)
        return package
    
    async def update_package(self, package_id: str, updates: dict) -> bool:
        """
        Aggiorna un pacchetto.
        
        Args:
            package_id: ID del pacchetto
            updates: Dict con campi da aggiornare
        
        Returns:
            True se aggiornato con successo
        """
        if self.packages_collection is None:
            await self.connect()
        
        result = await self.packages_collection.update_one(
            {"_id": package_id},
            {"$set": updates}
        )
        return result.modified_count > 0
    
    async def load_packages_from_yaml(self, yaml_path: str) -> int:
        """
        Carica pacchetti da file YAML. Aggiorna esistenti o crea nuovi.
        
        Args:
            yaml_path: Percorso del file YAML
        
        Returns:
            Numero di pacchetti caricati/aggiornati
        """
        if self.packages_collection is None:
            await self.connect()
        
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            packages_data = config.get("packages", [])
            count = 0
            
            for i, pkg_data in enumerate(packages_data):
                package = CreditPackage(
                    id=pkg_data.get("id", f"package_{i}"),
                    name=pkg_data.get("name", f"Package {i}"),
                    credits=pkg_data.get("credits", 10),
                    price_eur=pkg_data.get("price_eur", 0.0),
                    bonus_credits=pkg_data.get("bonus_credits", 0),
                    description=pkg_data.get("description"),
                    is_active=pkg_data.get("is_active", True),
                    sort_order=pkg_data.get("sort_order", i),
                    icon=pkg_data.get("icon"),
                )
                
                # Upsert: aggiorna se esiste, altrimenti crea
                doc = self._package_to_doc(package)
                await self.packages_collection.update_one(
                    {"_id": package.id},
                    {"$set": doc},
                    upsert=True
                )
                count += 1
            
            print(f"[CreditStore] Caricati {count} pacchetti da {yaml_path}", file=sys.stderr)
            return count
            
        except Exception as e:
            print(f"[CreditStore] Errore caricamento pacchetti da YAML: {e}", file=sys.stderr)
            raise
    
    # ==================== GESTIONE TRANSAZIONI ====================
    
    def _transaction_to_doc(self, tx: CreditTransaction) -> dict:
        """Converte CreditTransaction in documento MongoDB."""
        doc = {
            "_id": tx.id,
            "user_id": tx.user_id,
            "type": tx.type,
            "amount": tx.amount,
            "balance_after": tx.balance_after,
            "description": tx.description,
            "created_at": tx.created_at,
        }
        if tx.package_id:
            doc["package_id"] = tx.package_id
        if tx.metadata:
            doc["metadata"] = tx.metadata
        return doc
    
    @classmethod
    def _doc_to_transaction(cls, doc: dict) -> CreditTransaction:
        """Converte documento MongoDB in CreditTransaction."""
        return CreditTransaction(
            id=doc["_id"],
            user_id=doc["user_id"],
            type=doc["type"],
            amount=doc["amount"],
            balance_after=doc["balance_after"],
            package_id=doc.get("package_id"),
            description=doc["description"],
            metadata=doc.get("metadata"),
            created_at=doc["created_at"],
        )
    
    async def create_transaction(
        self,
        user_id: str,
        tx_type: str,
        amount: int,
        balance_after: int,
        description: str,
        package_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> CreditTransaction:
        """
        Crea una nuova transazione crediti.
        
        Args:
            user_id: ID utente
            tx_type: Tipo transazione (purchase, consumption, bonus, refund, reset)
            amount: Importo (positivo=aggiunta, negativo=consumo)
            balance_after: Saldo dopo la transazione
            description: Descrizione
            package_id: ID pacchetto (opzionale, per purchase)
            metadata: Dati extra (opzionale)
        
        Returns:
            CreditTransaction creata
        """
        if self.transactions_collection is None:
            await self.connect()
        
        tx = CreditTransaction(
            id=str(uuid.uuid4()),
            user_id=user_id,
            type=tx_type,
            amount=amount,
            balance_after=balance_after,
            package_id=package_id,
            description=description,
            metadata=metadata,
            created_at=datetime.utcnow(),
        )
        
        doc = self._transaction_to_doc(tx)
        await self.transactions_collection.insert_one(doc)
        
        print(f"[CreditStore] Transazione creata: {tx_type} {amount} crediti per utente {user_id}", file=sys.stderr)
        return tx
    
    async def get_user_transactions(
        self, 
        user_id: str, 
        skip: int = 0, 
        limit: int = 20,
        tx_type: Optional[str] = None
    ) -> Tuple[List[CreditTransaction], int]:
        """
        Recupera le transazioni di un utente.
        
        Args:
            user_id: ID utente
            skip: Offset per paginazione
            limit: Limite risultati
            tx_type: Filtra per tipo (opzionale)
        
        Returns:
            Tuple di (lista transazioni, totale)
        """
        if self.transactions_collection is None:
            await self.connect()
        
        query = {"user_id": user_id}
        if tx_type:
            query["type"] = tx_type
        
        # Conta totale
        total = await self.transactions_collection.count_documents(query)
        
        # Recupera transazioni
        transactions = []
        cursor = self.transactions_collection.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
        async for doc in cursor:
            transactions.append(self._doc_to_transaction(doc))
        
        return transactions, total
    
    # ==================== OPERAZIONI CREDITI ====================
    
    async def purchase_package(
        self, 
        user_id: str, 
        package_id: str,
        payment_verified: bool = True  # Per ora sempre True (free mode)
    ) -> Tuple[bool, str, int, Optional[CreditTransaction]]:
        """
        Acquista un pacchetto crediti per un utente.
        
        Args:
            user_id: ID utente
            package_id: ID pacchetto da acquistare
            payment_verified: Se il pagamento è stato verificato (per ora sempre True)
        
        Returns:
            Tuple di (successo, messaggio, nuovo_saldo, transazione)
        """
        if self.packages_collection is None:
            await self.connect()
        
        # Verifica pacchetto esiste e è attivo
        package = await self.get_package_by_id(package_id)
        if not package:
            return False, f"Pacchetto '{package_id}' non trovato", 0, None
        
        if not package.is_active:
            return False, f"Pacchetto '{package.name}' non più disponibile", 0, None
        
        # Verifica pagamento (per ora sempre verificato - free mode)
        if not payment_verified:
            return False, "Pagamento non verificato", 0, None
        
        # Calcola crediti totali (base + bonus)
        credits_to_add = package.credits + package.bonus_credits
        
        # Aggiorna saldo utente
        user_doc = await self.users_collection.find_one({"_id": user_id})
        if not user_doc:
            return False, f"Utente {user_id} non trovato", 0, None
        
        current_credits = user_doc.get("credits", user_doc.get("points", DEFAULT_CREDITS))
        new_balance = current_credits + credits_to_add
        
        # Aggiorna utente
        now = datetime.utcnow()
        await self.users_collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "credits": new_balance,
                    "points": new_balance,  # Mantieni sincronizzato per retrocompatibilità
                    "updated_at": now,
                },
                "$inc": {
                    "total_credits_purchased": credits_to_add,
                }
            }
        )
        
        # Crea transazione
        description = f"Acquisto pacchetto {package.name}"
        if package.bonus_credits > 0:
            description += f" (+{package.bonus_credits} bonus)"
        
        tx = await self.create_transaction(
            user_id=user_id,
            tx_type="purchase",
            amount=credits_to_add,
            balance_after=new_balance,
            description=description,
            package_id=package_id,
            metadata={
                "package_name": package.name,
                "base_credits": package.credits,
                "bonus_credits": package.bonus_credits,
                "price_eur": package.price_eur,
            }
        )
        
        print(f"[CreditStore] Acquisto completato: {user_id} ha acquistato {package.name} (+{credits_to_add} crediti)", file=sys.stderr)
        return True, f"Acquistato {package.name}: +{credits_to_add} crediti", new_balance, tx
    
    async def consume_credits(
        self, 
        user_id: str, 
        amount: int,
        description: str,
        metadata: Optional[dict] = None
    ) -> Tuple[bool, str, int]:
        """
        Consuma crediti per un utente.
        
        Args:
            user_id: ID utente
            amount: Quantità da consumare (valore positivo)
            description: Descrizione del consumo
            metadata: Dati extra (es. session_id)
        
        Returns:
            Tuple di (successo, messaggio, nuovo_saldo)
        """
        if self.users_collection is None:
            await self.connect()
        
        user_doc = await self.users_collection.find_one({"_id": user_id})
        if not user_doc:
            return False, f"Utente {user_id} non trovato", 0
        
        current_credits = user_doc.get("credits", user_doc.get("points", DEFAULT_CREDITS))
        
        if current_credits < amount:
            return False, f"Crediti insufficienti. Servono {amount} crediti, ne hai {current_credits}", current_credits
        
        new_balance = current_credits - amount
        
        # Aggiorna utente
        now = datetime.utcnow()
        await self.users_collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "credits": new_balance,
                    "points": new_balance,  # Mantieni sincronizzato
                    "updated_at": now,
                },
                "$inc": {
                    "total_credits_consumed": amount,
                }
            }
        )
        
        # Crea transazione
        await self.create_transaction(
            user_id=user_id,
            tx_type="consumption",
            amount=-amount,  # Negativo per consumo
            balance_after=new_balance,
            description=description,
            metadata=metadata
        )
        
        return True, f"Consumati {amount} crediti", new_balance
    
    async def add_bonus_credits(
        self, 
        user_id: str, 
        amount: int,
        description: str,
        metadata: Optional[dict] = None
    ) -> Tuple[bool, str, int, Optional[CreditTransaction]]:
        """
        Aggiunge crediti bonus a un utente.
        
        Args:
            user_id: ID utente
            amount: Quantità da aggiungere
            description: Descrizione del bonus
            metadata: Dati extra
        
        Returns:
            Tuple di (successo, messaggio, nuovo_saldo, transazione)
        """
        if self.users_collection is None:
            await self.connect()
        
        user_doc = await self.users_collection.find_one({"_id": user_id})
        if not user_doc:
            return False, f"Utente {user_id} non trovato", 0, None
        
        current_credits = user_doc.get("credits", user_doc.get("points", DEFAULT_CREDITS))
        new_balance = current_credits + amount
        
        # Aggiorna utente
        now = datetime.utcnow()
        await self.users_collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "credits": new_balance,
                    "points": new_balance,
                    "updated_at": now,
                }
            }
        )
        
        # Crea transazione
        tx = await self.create_transaction(
            user_id=user_id,
            tx_type="bonus",
            amount=amount,
            balance_after=new_balance,
            description=description,
            metadata=metadata
        )
        
        print(f"[CreditStore] Bonus aggiunto: {user_id} +{amount} crediti ({description})", file=sys.stderr)
        return True, f"Aggiunti {amount} crediti bonus", new_balance, tx
    
    async def get_user_credit_stats(self, user_id: str) -> dict:
        """
        Recupera statistiche crediti per un utente.
        
        Args:
            user_id: ID utente
        
        Returns:
            Dict con statistiche crediti
        """
        if self.users_collection is None:
            await self.connect()
        
        user_doc = await self.users_collection.find_one({"_id": user_id})
        if not user_doc:
            return {
                "credits": 0,
                "total_purchased": 0,
                "total_consumed": 0,
            }
        
        return {
            "credits": user_doc.get("credits", user_doc.get("points", DEFAULT_CREDITS)),
            "total_purchased": user_doc.get("total_credits_purchased", 0),
            "total_consumed": user_doc.get("total_credits_consumed", 0),
        }


# Istanza globale
_credit_store: Optional[CreditStore] = None


def get_credit_store() -> CreditStore:
    """Restituisce l'istanza globale del CreditStore."""
    global _credit_store
    if _credit_store is None:
        mongo_uri = os.getenv("MONGODB_URI", "mongodb://admin:admin123@localhost:27017/narrai?authSource=admin")
        _credit_store = CreditStore(mongo_uri)
        print(f"[CreditStore] Inizializzato con MongoDB URI: {mongo_uri.split('@')[-1] if '@' in mongo_uri else mongo_uri}", file=sys.stderr)
    return _credit_store
