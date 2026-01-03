import os
from dotenv import load_dotenv

# Carica .env PRIMA di importare l'app
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Test login
response = client.post(
    "/api/auth/login",
    json={"email": "pippo@gmail.com", "password": "warhammer"}
)

print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
