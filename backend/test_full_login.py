import asyncio
import os
from dotenv import load_dotenv

# Carica .env
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app.api.routers.auth import login, LoginRequest, create_session
from app.agent.user_store import get_user_store
from fastapi import Response

async def test():
    try:
        # Test create_session
        print("Testing create_session...")
        session_id = await create_session("test-user-id")
        print(f"Session created: {session_id}")
    except Exception as e:
        print(f"Error in create_session: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test())
