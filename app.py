from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

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
def run_processing(filename: str, username: str = Depends(authenticate)):
    """
    Processes a single PDF file by filename
    """
    try:
        main_logic(filename)
        
        return {
            "status": "Processing completed",
            "message": f"File {filename} processed successfully.",
            "user": username,
            "filename": filename
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
