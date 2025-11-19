"""
This module contains a FastAPI application for processing files with basic authentication.
"""
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import secrets
import traceback

# Import your existing logic
from main import main_logic

app = FastAPI()
security = HTTPBasic()

# Configure CORS to allow requests from different devices/origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Hardcoded credentials
EXPECTED_USERNAME = "admin"
EXPECTED_PASSWORD = "password123"

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Authenticates users based on HTTP Basic credentials.

    Args:
        credentials (HTTPBasicCredentials): The credentials provided in the request.

    Returns:
        str: The username if authentication is successful.

    Raises:
        HTTPException: If the username or password is invalid.
    """
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
    Processes a single PDF file by filename.

    Args:
        request (ProcessingRequest): The request body containing the filename.
        username (str): The authenticated username.

    Returns:
        dict: A dictionary indicating the status of the processing.

    Raises:
        HTTPException: If an error occurs during processing.
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
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )