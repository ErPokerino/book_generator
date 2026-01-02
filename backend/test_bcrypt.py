from passlib.context import CryptContext
import sys

try:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hash = pwd_context.hash("password123")
    print(f"Hash: {hash}")
    print("BCRYPT OK")
except Exception as e:
    print(f"Errore: {e}")
