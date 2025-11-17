from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import threading

# Import your existing logic
from main import main_logic

app = FastAPI()
security = HTTPBasic()

# Hardcoded credentials (recommended to move to config.ini or env variables)
EXPECTED_USERNAME = "admin"
EXPECTED_PASSWORD = "password123"

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    """Basic Authentication validator"""
    correct_username = secrets.compare_digest(credentials.username, EXPECTED_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, EXPECTED_PASSWORD)

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/api/run-processing")
def run_processing(username: str = Depends(authenticate)):
    """
    Triggers main_logic() when GET API is called
    """
    try:
        # Run main_logic in background to avoid blocking the API
        thread = threading.Thread(target=main_logic)
        thread.start()

        return {
            "status": "Processing started",
            "message": "main_logic() is running in background.",
            "user": username
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
