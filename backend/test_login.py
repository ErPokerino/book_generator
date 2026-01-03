import asyncio
import bcrypt
import os
from dotenv import load_dotenv

# Carica .env
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app.agent.user_store import get_user_store

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        password_bytes = plain_password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception as e:
        print(f'Exception during verify: {e}')
        return False

async def test():
    store = get_user_store()
    await store.connect()
    user = await store.get_user_by_email('pippo@gmail.com')
    if user:
        print(f'User found: {user.email}')
        print(f'Hash: {user.password_hash}')
        # Prova varie password
        for pwd in ['warhammer', 'Warhammer', 'warhammer40k']:
            result = verify_password(pwd, user.password_hash)
            print(f'Password "{pwd}": {result}')
    else:
        print('User not found')

asyncio.run(test())
