"""Servizio per gestione pagamenti.

Questo servizio è un STUB per la modalità gratuita.
In futuro sarà sostituito con un'integrazione reale (Stripe, PayPal, etc.).
"""
from typing import Optional, Dict, Any
from datetime import datetime

from app.core.logging import get_logger


logger = get_logger("payment-service")


class PaymentService:
    """
    Servizio per gestione pagamenti.
    
    NOTA: Attualmente è uno stub che simula pagamenti gratuiti.
    Per integrare un gateway reale (Stripe, PayPal), implementare i metodi:
    - create_checkout_session()
    - verify_payment()
    - handle_webhook()
    """
    
    def __init__(self, mode: str = "free"):
        """
        Inizializza il servizio pagamenti.
        
        Args:
            mode: Modalità operativa
                - "free": Tutti i pagamenti sono gratuiti (default)
                - "stripe": Integrazione Stripe (futuro)
                - "paypal": Integrazione PayPal (futuro)
        """
        self.mode = mode
        logger.info("Payment service inizializzato", context={"mode": mode})
    
    async def create_checkout_session(
        self,
        user_id: str,
        package_id: str,
        amount: float,
        currency: str = "EUR",
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Crea una sessione di checkout per il pagamento.
        
        In modalità "free", restituisce sempre successo immediato.
        In futuro, con Stripe/PayPal, restituirà un URL di redirect.
        
        Args:
            user_id: ID dell'utente che effettua l'acquisto
            package_id: ID del pacchetto da acquistare
            amount: Importo in EUR
            currency: Valuta (default: EUR)
            success_url: URL di redirect dopo pagamento riuscito
            cancel_url: URL di redirect dopo annullamento
        
        Returns:
            Dict con:
            - success: bool
            - redirect_url: URL per il checkout (None in modalità free)
            - session_id: ID sessione pagamento (None in modalità free)
            - message: Messaggio descrittivo
        """
        if self.mode == "free":
            # Modalità gratuita: simula pagamento immediato
            logger.info(
                "Checkout simulato in free mode",
                context={"user_id": user_id, "package_id": package_id},
            )
            return {
                "success": True,
                "redirect_url": None,
                "session_id": None,
                "message": "Modalità gratuita - nessun pagamento richiesto"
            }
        
        # TODO: Implementare integrazione Stripe/PayPal
        # Esempio Stripe:
        # import stripe
        # stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        # 
        # checkout_session = stripe.checkout.Session.create(
        #     payment_method_types=["card"],
        #     line_items=[{
        #         "price_data": {
        #             "currency": currency.lower(),
        #             "unit_amount": int(amount * 100),  # Stripe usa centesimi
        #             "product_data": {"name": f"Pacchetto crediti {package_id}"},
        #         },
        #         "quantity": 1,
        #     }],
        #     mode="payment",
        #     success_url=success_url,
        #     cancel_url=cancel_url,
        #     client_reference_id=user_id,
        #     metadata={"package_id": package_id},
        # )
        # return {
        #     "success": True,
        #     "redirect_url": checkout_session.url,
        #     "session_id": checkout_session.id,
        #     "message": "Sessione checkout creata"
        # }
        
        return {
            "success": False,
            "redirect_url": None,
            "session_id": None,
            "message": f"Modalità {self.mode} non implementata"
        }
    
    async def verify_payment(
        self,
        user_id: str,
        package_id: str,
        amount: float,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verifica che un pagamento sia stato completato.
        
        In modalità "free", restituisce sempre verificato.
        
        Args:
            user_id: ID dell'utente
            package_id: ID del pacchetto acquistato
            amount: Importo atteso
            session_id: ID sessione pagamento (opzionale)
        
        Returns:
            Dict con:
            - verified: bool - Se il pagamento è verificato
            - message: Messaggio descrittivo
            - payment_id: ID del pagamento (per riferimento)
        """
        if self.mode == "free":
            # Modalità gratuita: sempre verificato
            logger.info(
                "Pagamento verificato in free mode",
                context={"user_id": user_id, "package_id": package_id},
            )
            return {
                "verified": True,
                "message": "Modalità gratuita - pagamento automaticamente verificato",
                "payment_id": f"free_{user_id}_{package_id}_{datetime.utcnow().timestamp()}"
            }
        
        # TODO: Implementare verifica Stripe/PayPal
        # Esempio Stripe:
        # import stripe
        # stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        # 
        # try:
        #     session = stripe.checkout.Session.retrieve(session_id)
        #     if session.payment_status == "paid":
        #         return {
        #             "verified": True,
        #             "message": "Pagamento verificato con Stripe",
        #             "payment_id": session.payment_intent
        #         }
        # except stripe.error.StripeError as e:
        #     return {
        #         "verified": False,
        #         "message": f"Errore verifica Stripe: {str(e)}",
        #         "payment_id": None
        #     }
        
        return {
            "verified": False,
            "message": f"Modalità {self.mode} non implementata",
            "payment_id": None
        }
    
    async def handle_webhook(
        self,
        payload: bytes,
        signature: str
    ) -> Dict[str, Any]:
        """
        Gestisce webhook dal gateway di pagamento.
        
        In modalità "free", non fa nulla.
        
        Args:
            payload: Body della richiesta webhook
            signature: Firma per verifica autenticità
        
        Returns:
            Dict con risultato dell'elaborazione
        """
        if self.mode == "free":
            return {
                "success": True,
                "message": "Modalità gratuita - webhook ignorato"
            }
        
        # TODO: Implementare gestione webhook Stripe/PayPal
        # Esempio Stripe:
        # import stripe
        # endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        # 
        # try:
        #     event = stripe.Webhook.construct_event(payload, signature, endpoint_secret)
        #     
        #     if event["type"] == "checkout.session.completed":
        #         session = event["data"]["object"]
        #         user_id = session["client_reference_id"]
        #         package_id = session["metadata"]["package_id"]
        #         
        #         # Accredita i crediti all'utente
        #         credit_store = get_credit_store()
        #         await credit_store.purchase_package(user_id, package_id, payment_verified=True)
        #         
        #         return {"success": True, "message": "Crediti accreditati"}
        #         
        # except ValueError:
        #     return {"success": False, "message": "Payload non valido"}
        # except stripe.error.SignatureVerificationError:
        #     return {"success": False, "message": "Firma non valida"}
        
        return {
            "success": False,
            "message": f"Modalità {self.mode} non implementata"
        }
    
    async def refund_payment(
        self,
        payment_id: str,
        amount: Optional[float] = None,
        reason: str = "requested_by_customer"
    ) -> Dict[str, Any]:
        """
        Effettua un rimborso per un pagamento.
        
        In modalità "free", restituisce sempre successo.
        
        Args:
            payment_id: ID del pagamento da rimborsare
            amount: Importo da rimborsare (None = totale)
            reason: Motivo del rimborso
        
        Returns:
            Dict con risultato del rimborso
        """
        if self.mode == "free":
            logger.info("Rimborso simulato in free mode", context={"payment_id": payment_id})
            return {
                "success": True,
                "refund_id": f"refund_{payment_id}",
                "message": "Modalità gratuita - rimborso simulato"
            }
        
        # TODO: Implementare rimborso Stripe/PayPal
        
        return {
            "success": False,
            "refund_id": None,
            "message": f"Modalità {self.mode} non implementata"
        }


# Istanza globale
_payment_service: Optional[PaymentService] = None


def get_payment_service() -> PaymentService:
    """Restituisce l'istanza globale del PaymentService."""
    global _payment_service
    if _payment_service is None:
        # Per ora sempre in modalità free
        # In futuro leggere da env: os.getenv("PAYMENT_MODE", "free")
        _payment_service = PaymentService(mode="free")
    return _payment_service
