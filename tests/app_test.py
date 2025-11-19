"""
This module contains unit tests for the FastAPI application defined in `app.py`.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from app import app, EXPECTED_USERNAME, EXPECTED_PASSWORD
client = TestClient(app)

# ----------------------------------------
# Helper function to generate basic-auth header
# ----------------------------------------
import base64
def basic_auth_header(username, password):
    """
    Generates an HTTP Basic Authentication header.

    Args:
        username (str): The username for authentication.
        password (str): The password for authentication.

    Returns:
        dict: A dictionary containing the Authorization header.
    """
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


# ======================================================
# TESTS
# ======================================================

def test_auth_success():
    """Test successful Basic Authentication.

    Verifies that a request with correct credentials does not result in a 401 Unauthorized status.
    """
    headers = basic_auth_header(EXPECTED_USERNAME, EXPECTED_PASSWORD)

    response = client.post("/api/run-processing", json={"filename": "sample.pdf"}, headers=headers)

    assert response.status_code != 401  # must NOT be unauthorized


def test_auth_failure_wrong_username():
    """Test authentication fails with wrong username.

    Verifies that a request with an incorrect username results in a 401 Unauthorized status.
    """
    headers = basic_auth_header("wronguser", EXPECTED_PASSWORD)

    response = client.post("/api/run-processing", json={"filename": "sample.pdf"}, headers=headers)

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_auth_failure_wrong_password():
    """Test authentication fails with wrong password.

    Verifies that a request with an incorrect password results in a 401 Unauthorized status.
    """
    headers = basic_auth_header(EXPECTED_USERNAME, "wrongpass")

    response = client.post("/api/run-processing", json={"filename": "sample.pdf"}, headers=headers)

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


@patch("app.main_logic")   # IMPORTANT: use correct module path
def test_successful_processing(mock_main_logic):
    """Test successful file processing.

    Mocks the main_logic and verifies that the processing endpoint returns a 200 OK status
    and the correct response body.
    """
    
    mock_main_logic.return_value = None  # main_logic doesn't return anything

    headers = basic_auth_header(EXPECTED_USERNAME, EXPECTED_PASSWORD)

    response = client.post("/api/run-processing", json={"filename": "doc1.pdf"}, headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "Processing completed"
    assert response.json()["filename"] == "doc1.pdf"
    assert response.json()["user"] == EXPECTED_USERNAME
    
    mock_main_logic.assert_called_once_with("doc1.pdf")


@patch("app.main_logic")
def test_processing_exception(mock_main_logic):
    """Test server error when main_logic raises exception.

    Mocks the main_logic to raise an exception and verifies that the processing endpoint
    returns a 500 Internal Server Error status.
    """
    
    mock_main_logic.side_effect = Exception("Something went wrong")

    headers = basic_auth_header(EXPECTED_USERNAME, EXPECTED_PASSWORD)

    response = client.post("/api/run-processing", json={"filename": "doc2.pdf"}, headers=headers)

    assert response.status_code == 500
    assert response.json()["detail"] == "Something went wrong"
