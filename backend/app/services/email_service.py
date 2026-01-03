"""Servizio email per invio notifiche."""
import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional


class EmailService:
    """Servizio per invio email tramite SMTP."""
    
    def __init__(self):
        """Inizializza il servizio email con credenziali da env."""
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        
        if not self.smtp_user or not self.smtp_password:
            print("[EmailService] ATTENZIONE: Credenziali SMTP non configurate", file=sys.stderr)
    
    def _get_verification_email_html(self, user_name: str, verification_url: str) -> str:
        """Genera HTML per email di verifica."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verifica il tuo account NarrAI</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f5;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td style="padding: 40px 0;">
                <table role="presentation" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; text-align: center;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 32px;">📚 NarrAI</h1>
                            <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0; font-size: 16px;">Il tuo assistente per la scrittura</p>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <h2 style="color: #1f2937; margin: 0 0 20px 0; font-size: 24px;">Ciao {user_name}! 👋</h2>
                            <p style="color: #4b5563; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">
                                Grazie per esserti registrato su NarrAI! Per completare la registrazione e iniziare a creare i tuoi libri, clicca sul pulsante qui sotto per verificare il tuo indirizzo email.
                            </p>
                            
                            <!-- Button -->
                            <table role="presentation" style="margin: 30px 0;">
                                <tr>
                                    <td style="border-radius: 8px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                                        <a href="{verification_url}" target="_blank" style="display: inline-block; padding: 16px 32px; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600;">
                                            ✅ Verifica Email
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            
                            <p style="color: #6b7280; font-size: 14px; line-height: 1.6; margin: 20px 0 0 0;">
                                Se il pulsante non funziona, copia e incolla questo link nel tuo browser:
                            </p>
                            <p style="color: #667eea; font-size: 14px; word-break: break-all; margin: 10px 0 0 0;">
                                {verification_url}
                            </p>
                            
                            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                            
                            <p style="color: #9ca3af; font-size: 12px; margin: 0;">
                                ⏰ Questo link scade tra 24 ore.<br>
                                Se non hai richiesto questa registrazione, puoi ignorare questa email.
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9fafb; padding: 20px; text-align: center;">
                            <p style="color: #9ca3af; font-size: 12px; margin: 0;">
                                © 2026 NarrAI - Tutti i diritti riservati
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    
    def _get_verification_email_text(self, user_name: str, verification_url: str) -> str:
        """Genera testo plain per email di verifica."""
        return f"""Ciao {user_name}!

Grazie per esserti registrato su NarrAI!

Per completare la registrazione e iniziare a creare i tuoi libri, clicca sul link qui sotto per verificare il tuo indirizzo email:

{verification_url}

Questo link scade tra 24 ore.

Se non hai richiesto questa registrazione, puoi ignorare questa email.

---
NarrAI - Il tuo assistente per la scrittura
"""
    
    def send_verification_email(self, to_email: str, token: str, user_name: str) -> bool:
        """
        Invia email di verifica.
        
        Args:
            to_email: Email destinatario
            token: Token di verifica
            user_name: Nome utente
        
        Returns:
            True se inviata con successo
        """
        if not self.smtp_user or not self.smtp_password:
            print(f"[EmailService] Skip invio email - credenziali non configurate", file=sys.stderr)
            return False
        
        verification_url = f"{self.frontend_url}/verify?token={token}"
        
        try:
            # Crea messaggio multipart (HTML + testo)
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "📚 Verifica il tuo account NarrAI"
            msg["From"] = f"NarrAI <{self.smtp_user}>"
            msg["To"] = to_email
            
            # Aggiungi versione testo e HTML
            text_part = MIMEText(self._get_verification_email_text(user_name, verification_url), "plain", "utf-8")
            html_part = MIMEText(self._get_verification_email_html(user_name, verification_url), "html", "utf-8")
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Connetti e invia
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.smtp_user, to_email, msg.as_string())
            
            print(f"[EmailService] Email di verifica inviata a: {to_email}", file=sys.stderr)
            return True
            
        except Exception as e:
            print(f"[EmailService] ERRORE invio email a {to_email}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return False
    
    def send_password_reset_email(self, to_email: str, token: str, user_name: str) -> bool:
        """
        Invia email per reset password.
        
        Args:
            to_email: Email destinatario
            token: Token di reset
            user_name: Nome utente
        
        Returns:
            True se inviata con successo
        """
        if not self.smtp_user or not self.smtp_password:
            print(f"[EmailService] Skip invio email reset - credenziali non configurate", file=sys.stderr)
            return False
        
        reset_url = f"{self.frontend_url}/reset-password?token={token}"
        
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "🔐 Reset password NarrAI"
            msg["From"] = f"NarrAI <{self.smtp_user}>"
            msg["To"] = to_email
            
            text_content = f"""Ciao {user_name},

Hai richiesto il reset della password per il tuo account NarrAI.

Clicca sul link qui sotto per impostare una nuova password:
{reset_url}

Questo link scade tra 24 ore.

Se non hai richiesto il reset, puoi ignorare questa email.

---
NarrAI - Il tuo assistente per la scrittura
"""
            
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f5;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td style="padding: 40px 0;">
                <table role="presentation" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                    <tr>
                        <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; text-align: center;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 32px;">📚 NarrAI</h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px;">
                            <h2 style="color: #1f2937; margin: 0 0 20px 0;">Ciao {user_name}! 🔐</h2>
                            <p style="color: #4b5563; font-size: 16px; line-height: 1.6;">
                                Hai richiesto il reset della password. Clicca il pulsante qui sotto per impostarne una nuova:
                            </p>
                            <table role="presentation" style="margin: 30px 0;">
                                <tr>
                                    <td style="border-radius: 8px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                                        <a href="{reset_url}" target="_blank" style="display: inline-block; padding: 16px 32px; color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600;">
                                            🔑 Reset Password
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            <p style="color: #9ca3af; font-size: 12px;">
                                ⏰ Questo link scade tra 24 ore.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
            
            msg.attach(MIMEText(text_content, "plain", "utf-8"))
            msg.attach(MIMEText(html_content, "html", "utf-8"))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.smtp_user, to_email, msg.as_string())
            
            print(f"[EmailService] Email reset password inviata a: {to_email}", file=sys.stderr)
            return True
            
        except Exception as e:
            print(f"[EmailService] ERRORE invio email reset a {to_email}: {e}", file=sys.stderr)
            return False


# Istanza globale
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Restituisce l'istanza globale del EmailService."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
