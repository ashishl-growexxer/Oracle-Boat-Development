import pytest
from unittest.mock import MagicMock, patch
from PIL import Image
from io import BytesIO
import json
import base64
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from extract_headers_and_lines import extract_values_only, extract_header_df, extract_line_items_df, extract_values_from_dict_file, extract_po_from_file
from inference_code import OCIModel


@pytest.fixture
def mock_oci_client():
    """Returns a mocked OCI client."""
    mock = MagicMock()
    return mock
@pytest.fixture
def model(mock_oci_client):
    """Create OCIModel with mocked client + mocked config loader + mocked initializer."""
    with patch("oci.config.from_file", return_value={"dummy": "config"}), \
         patch("oci.generative_ai_inference.GenerativeAiInferenceClient", return_value=mock_oci_client):
        m = OCIModel()
        m.client = mock_oci_client  # override client
        return m

# ------------------------------------------------
# Test _clean_and_parse_json
# ------------------------------------------------
def test_clean_and_parse_json_normal(model):
    text = '{"name": "Ashish", "value": 10}'
    result = model._clean_and_parse_json(text)
    assert result["cleaned_json"] == {"name": "Ashish", "value": 10}
def test_clean_and_parse_json_with_markdown(model):
    text = """```json
    {"a": 1}
    ```"""
    result = model._clean_and_parse_json(text)
    assert result["cleaned_json"] == {"a": 1}
def test_clean_and_parse_json_invalid(model):
    text = "{invalid json"
    result = model._clean_and_parse_json(text)
    assert "error" in result
# ------------------------------------------------
# Test _format_oci_response
# ------------------------------------------------
def test_format_oci_response(model):
    mock_response = MagicMock()
    mock_response.data = {
        "chat_response": {
            "choices": [{
                "message": {
                    "content": [{"text": '{"a": 1}'}]
                }
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }
    }
    formatted = model._format_oci_response(mock_response, 100, 102)
    assert formatted["data"] == {"a": 1}
    assert formatted["token_usage"]["prompt_tokens"] == 10
    assert formatted["response_time_seconds"] == 2
# ------------------------------------------------
# Test infer_with_images (mock OCI)
# ------------------------------------------------
@patch("oci.generative_ai_inference.models.ChatDetails")
@patch("oci.generative_ai_inference.models.GenericChatRequest")
@patch("oci.generative_ai_inference.models.Message")
@patch("oci.generative_ai_inference.models.TextContent")
@patch("oci.generative_ai_inference.models.ImageContent")
@patch("oci.generative_ai_inference.models.ImageUrl")
@patch("oci.generative_ai_inference.models.OnDemandServingMode")
def test_infer_with_images_success(
    mock_serving_mode,
    mock_image_url,
    mock_image_content,
    mock_text_content,
    mock_message,
    mock_chat_request,
    mock_chat_details,
    model,
    mock_oci_client
):
    # Prepare a fake PIL image
    img = Image.new("RGB", (100, 100))
    # Mock OCI response
    mock_response = MagicMock()
    mock_response.data = {
        "chat_response": {
            "choices": [{
                "message": {
                    "content": [{"text": '{"ok": true}'}]
                }
            }],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
        }
    }
    mock_oci_client.chat.return_value = mock_response
    result = model.infer_with_images([img], prompt="hello")
    assert "data" in result
    assert result["data"] == {"ok": True}
    assert "response_time_seconds" in result
def test_infer_with_images_no_images(model):
    result = model.infer_with_images([], prompt="test")
    assert result["error"] == "No images provided"


import json
import pytest
from unittest.mock import MagicMock


# ------------------------------
# Helper class for attribute-based mocks
# ------------------------------
class Obj:
    def __init__(self, **entries):
        for k, v in entries.items():
            setattr(self, k, v)


# ------------------------------
# Tests for _extract_text_from_response
# ------------------------------
def test_extract_text_from_response_dict(model):
    mock_response = MagicMock()
    mock_response.data = {
        "chat_response": {
            "choices": [{
                "message": {
                    "content": [{"text": "Hello world"}]
                }
            }]
        }
    }
    assert model._extract_text_from_response(mock_response) == "Hello world"


def test_extract_text_from_response_string_json(model):
    json_string = json.dumps({
        "chat_response": {
            "choices": [{
                "message": {
                    "content": [{"text": "Extracted"}]
                }
            }]
        }
    })
    mock_response = MagicMock()
    mock_response.data = json_string

    assert model._extract_text_from_response(mock_response) == "Extracted"


def test_extract_text_from_response_string_non_json(model):
    mock_response = MagicMock()
    mock_response.data = "non-json-string"
    # Non-JSON strings do NOT contain chat_response → expected output: empty string
    assert model._extract_text_from_response(mock_response) == ""



def test_extract_text_from_response_attribute_objects(model):
    mock_response = MagicMock()

    mock_response.data = Obj(
        chat_response=Obj(
            choices=[Obj(
                message=Obj(
                    content=[Obj(text="From attributes")]
                )
            )]
        )
    )
    assert model._extract_text_from_response(mock_response) == "From attributes"


def test_extract_text_from_response_no_choices(model):
    mock_response = MagicMock()
    mock_response.data = {"chat_response": {"choices": []}}

    assert model._extract_text_from_response(mock_response) == ""


def test_extract_text_from_response_missing_message(model):
    mock_response = MagicMock()
    mock_response.data = {
        "chat_response": {
            "choices": [{}]  # no message
        }
    }
    assert model._extract_text_from_response(mock_response) == ""


def test_extract_text_from_response_missing_content(model):
    mock_response = MagicMock()
    mock_response.data = {
        "chat_response": {
            "choices": [{
                "message": {}  # no content list
            }]
        }
    }
    assert model._extract_text_from_response(mock_response) == ""


def test_extract_text_from_response_empty_content(model):
    mock_response = MagicMock()
    mock_response.data = {
        "chat_response": {
            "choices": [{
                "message": {"content": []}
            }]
        }
    }
    assert model._extract_text_from_response(mock_response) == ""


def test_extract_text_from_response_non_string_text(model):
    mock_response = MagicMock()
    mock_response.data = {
        "chat_response": {
            "choices": [{
                "message": {"content": [{"text": 12345}]}
            }]
        }
    }
    assert model._extract_text_from_response(mock_response) == "12345"


def test_extract_text_from_response_exception(model):
    # Force exception inside function
    mock_response = MagicMock()
    mock_response.data = Obj()
    del mock_response.data  # accessing .data will raise AttributeError

    assert model._extract_text_from_response(mock_response) == ""

