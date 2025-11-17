from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import secrets

# Import your existing logic
from main import main_logic

app = FastAPI()
security = HTTPBasic()

# Configure CORS to allow requests from different devices/origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins. For production, specify exact origins: ["http://localhost:3000", "https://yourdomain.com"]
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allows all headers
)

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


class ProcessingRequest(BaseModel):
    """Request model for processing endpoint"""
    filename: str

@app.post("/api/run-processing")
def run_processing(request: ProcessingRequest, username: str = Depends(authenticate)):
    """
    Processes a single PDF file by filename
    """
    try:
        filename = request.filename
        print(f"Received request to process file: {filename}")
        main_logic(filename)
        
        return {
            "status": "Processing completed",
            "message": f"File {request.filename} processed successfully.",
            "user": username,
            "filename": request.filename
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
