"""
This is Inference code used for Declaring OCI MOdel whose function,
is to infer from LLM and return appropriate response.
"""
import oci
import base64
import time
from typing import Optional, List, Dict, Any
from io import BytesIO
from PIL import Image
from pdf2image import convert_from_path
from PIL import Image, ImageTk
import io, base64
import json
import traceback
import re

def safe_get(obj, key, default=None):
    """Get key from dict or attribute from object."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default) if hasattr(obj, key) else default

def load_if_json(obj):
    """Decode JSON string if applicable."""
    if isinstance(obj, str):
        try:
            return json.loads(obj)
        except json.JSONDecodeError:
            return obj
    return obj

def first_or_none(item):
    """Return first element if list, else item."""
    if isinstance(item, list):
        return item[0] if item else None
    return item

def  prepare_token_usage(usage):
    """Prepare token usage dictionary."""
    return {
        "prompt_tokens": usage.get("prompt_tokens") if isinstance(usage, dict)
        else getattr(usage, 'prompt_tokens', None),
        "completion_tokens": usage.get("completion_tokens") if isinstance(usage, dict)
        else getattr(usage, 'completion_tokens', None),
        "total_tokens": usage.get("total_tokens") if isinstance(usage, dict)
        else getattr(usage, 'total_tokens', None),
    }


class OCIModel(object):
    """
    OCI Generative AI model interface with memory management.
    Follows the same pattern as BedrockModel for consistency.
    Supports both normal inference and image-based inference with proper
    resource cleanup for images and buffers.
    """
    def __init__(
        self,
        config_path: str = None,
        model_id: str = None,
        compartment_id: str = None,
        config_profile: str = "DEFAULT",
        endpoint: str = None
    ):
        """
        Initialize OCI Generative AI model interface.
        Args:
            config_path: Path to OCI config file (default: ~/.oci/config)
            model_id: OCI model identifier/OCID
            compartment_id: OCI compartment OCID
            config_profile: OCI config profile name (default: "DEFAULT")
            endpoint: OCI service endpoint (optional, will use default if not provided)
        """
        self.config_profile = config_profile
        self.config_path = "./config.ini"
        self.model_id = (
            "ocid1.generativeaimodel.oc1.us-chicago-1."
            "amaaaaaask7dceyayjawvuonfkw2ua4bob4rlnnlhs522pafbglivtwlfzta"
        )
        self.compartment_id = "ocid1.compartment.oc1..aaaaaaaa7wyo7euk2wfekpv36obtfbqgupxeb5yylivifscxseudvwwp2ixa"
        # Load configuration
        self.config = self._load_config()
        self.max_tokens = self.config.get("max_tokens", 4096)
        # Initialize client
        self.client = self._initialize_client(endpoint)

    @staticmethod
    def _load_config() -> Dict[str, Any]:
        """
        Load OCI configuration.
        Returns:
            dict: OCI configuration parameters
        """
        print("Loading OCI Generative AI configuration")
        return {
            "max_tokens": 4096,
            "timeout": (10, 240),
        }

    def _initialize_client(self, endpoint: str = None) -> oci.generative_ai_inference.GenerativeAiInferenceClient:
        """
        Initialize OCI Generative AI Inference client.
        Args:
            endpoint: Optional service endpoint (uses default if not provided)
        Returns:
            oci.generative_ai_inference.GenerativeAiInferenceClient: Configured OCI client
        """
        print("Initializing OCI Generative AI Inference client")
        # Load OCI config
        oci_config = oci.config.from_file(self.config_path, self.config_profile)
        # Default endpoint if not provided
        if endpoint is None:
            endpoint = "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com"
        # Create client with retry strategy and timeout
        client = oci.generative_ai_inference.GenerativeAiInferenceClient(
            config=oci_config,
            service_endpoint=endpoint,
            retry_strategy=oci.retry.NoneRetryStrategy(),
            timeout=self.config["timeout"]
        )
        return client

    @staticmethod
    def extract_text(input_text):
        if isinstance(input_text, str):
            return input_text
        else:
            return str(input_text)

    def _extract_text_from_response(self,chat_response) -> str:
        """
        Extract text content from OCI chat response with reduced cognitive complexity.
        SonarQube-friendly: only one return, fewer branches.
        """


        result = ""

        try:
            data = load_if_json(chat_response.data)

            chat_data = safe_get(data, "chat_response", data)
            choices = safe_get(chat_data, "choices", [])

            first_choice = first_or_none(choices)
            if first_choice is None:
                return result

            message = safe_get(first_choice, "message", {})
            content_list = safe_get(message, "content", [])

            first_content = first_or_none(content_list)
            if first_content is None:
                return result

            text = safe_get(first_content, "text", "")
            result = self.extract_text(text)


        except Exception as e:
            # swallow and return default result
            print(f"Encountered Error {e}")

        return result

    def _clean_and_parse_json(self, text: str) -> Dict[str, Any]:
        """
        Clean and parse JSON response from LLAMA model with SonarQube-friendly structure.
        """

        result: Dict[str, Any] = {}   # <-- single return value container

        if not text:
            result = {"error": "Empty response from LLAMA model"}
            return result

        # Try parsing top-level JSON first
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and "chat_response" in parsed:
                obj = type("obj", (object,), {"data": parsed})
                text = self._extract_text_from_response(obj())
        except (json.JSONDecodeError, AttributeError):
            pass

        # Remove markdown fenced code blocks
        json_text = re.sub(r"^```json\s*\n|\n\s*```$", "", text, flags=re.MULTILINE).strip()
        json_text = re.sub(r"^```\s*\n|\n\s*```$", "", json_text, flags=re.MULTILINE).strip()

        if not json_text:
            msg = "LLAMA extraction failed: Empty response after processing"
            print("LLAMA returned empty response after cleaning")
            result = {"error": msg}
            return result

        # Try final JSON parse
        try:
            cleaned_json = json.loads(json_text)
            result = {"cleaned_json": cleaned_json}
        except json.JSONDecodeError as e:
            print(f"Failed to parse LLAMA response as JSON: {e}")
            print(f"Raw response preview: {json_text}...")
            result = {"error": f"LLAMA extraction failed: Invalid JSON response - {str(e)}"}

        return result


    def _format_oci_response(
        self,
        chat_response,
        start_time: float,
        end_time: float,
        validate_empty: bool = True,
    ) -> Dict[str, Any]:
        """
        Format OCI response with data, token usage, and timing.
        Similar to BedrockModel._format_bedrock_response().
        Args:
            chat_response: OCI chat response object
            start_time: Start time for calculating response time
            end_time: End time for calculating response time
            validate_empty: Whether to validate for empty response
        Returns:
            dict: Formatted response dictionary with cleaned JSON
        """
        # Extract text from response
        raw_text = self._extract_text_from_response(chat_response)
        # Validate response
        if validate_empty and not raw_text:
            print("OCI returned empty response")
            return {"error": "Empty response from OCI model"}
        # Clean and parse JSON
        parse_result = self._clean_and_parse_json(raw_text)
        if "error" in parse_result:
            return parse_result
        # Extract token usage from response
        token_usage = {}
        try:
            response_data = chat_response.data
            if isinstance(response_data, dict):
                usage = response_data.get("chat_response", {}).get("usage", {})
            else:
                has_chat_resp = hasattr(response_data, "chat_response")
                has_usage = has_chat_resp and hasattr(response_data.chat_response, "usage")
                usage = (
                    response_data.chat_response.usage
                    if has_usage
                    else {}
                )
            if usage:
                token_usage = prepare_token_usage(usage)
        except Exception as e:
            print(f"Could not extract token usage: {e}")
        return {
            "data": parse_result["cleaned_json"],
            "token_usage": token_usage,
            "response_time_seconds": round(end_time - start_time, 2),
        }

    def infer_with_images(
        self,
        images: List[Image.Image],
        prompt: str,
        max_tokens: int = None,
        temperature: float = 0.2,
        frequency_penalty: float = 0,
        presence_penalty: float = 0,
        top_p: float = 0.75
    ) -> Dict[str, Any]:
        """
        Run inference on pre-converted images (PIL Image objects).
        This follows the same pattern as BedrockModel.infer_with_images() for consistency.
        The function processes PIL Images, encodes them to base64, and sends them to OCI.
        Args:
            images: List of PIL Image objects
            prompt: Prompt text
            max_tokens: Maximum tokens in response (uses self.max_tokens if not provided)
            temperature: Sampling temperature
            frequency_penalty: Frequency penalty
            presence_penalty: Presence penalty
            top_p: Top-p sampling parameter
        Returns:
            dict: Model response with data, response_time_seconds, or error
        """
        print("Running OCI Generative AI inference with images")
        if not images:
            return {"error": "No images provided"}
        if max_tokens is None:
            max_tokens = self.max_tokens
        buffers = []
        try:
            chat_detail = oci.generative_ai_inference.models.ChatDetails()
            print(f"Processing {len(images)} images")
            # Create chat detail
            content_list = []
            text_content = oci.generative_ai_inference.models.TextContent()
            text_content.text = prompt
            content_list.append(text_content)
            messages = []
            # Create message
            message = oci.generative_ai_inference.models.Message()
            message.role = "USER"
            message.content = content_list
            messages.append(message)
            # Add each image (following Bedrock pattern: iterate through images)
            for page_num, image in enumerate(images, start=1):
                buffer = BytesIO()
                buffers.append(buffer)
                try:
                    # Save image to buffer and encode to base64
                    image.save(buffer, format="JPEG")
                    buffer.seek(0)
                    image_bytes = buffer.getvalue()
                    image_base64 = base64.b64encode(image_bytes).decode()
                    print(f"Added image {page_num} to content (size: {len(image_bytes)} bytes)")
                    image_content = oci.generative_ai_inference.models.ImageContent()
                    given_image_url = oci.generative_ai_inference.models.ImageUrl()
                    given_image_url.url =  f"data:image/png;base64,{image_base64}"
                    image_content.image_url = given_image_url
                    image_message = oci.generative_ai_inference.models.Message()
                    image_message.role = "USER"
                    image_message.content = [image_content]
                    messages.append(image_message)
                except Exception as e:
                    print(f"Failed to process page {page_num}: {e}")
                    continue
            # Create message (same structure as Bedrock)
            message = oci.generative_ai_inference.models.Message()
            message.role = "USER"
            message.content = content_list
            messages.append(message)
            # Create chat request
            chat_request = oci.generative_ai_inference.models.GenericChatRequest()
            chat_request.api_format = oci.generative_ai_inference.models.BaseChatRequest.API_FORMAT_GENERIC
            chat_request.messages = messages
            chat_request.max_tokens = max_tokens
            chat_request.temperature = temperature
            chat_request.frequency_penalty = frequency_penalty
            chat_request.presence_penalty = presence_penalty
            chat_request.top_p = top_p
            # Set serving mode
            chat_detail.serving_mode = oci.generative_ai_inference.models.OnDemandServingMode(model_id=self.model_id)
            chat_detail.chat_request = chat_request
            chat_detail.compartment_id = self.compartment_id
            # Call OCI API (using self.client like BedrockModel)
            start_time = time.time()
            chat_response = self.client.chat(chat_detail)
            end_time = time.time()
            return self._format_oci_response(chat_response, start_time, end_time, validate_empty=True)
        except Exception as e:
            print(f"OCI image inference error: {e}")
            traceback.print_exc()
            return {"error": str(e)}
        finally:
            # Cleanup resources - but DON'T close images as they may be reused (same as Bedrock)
            for buffer in buffers:
                try:
                    if buffer and not buffer.closed:
                        buffer.close()
                except Exception as e:
                    print(f"Failed to close buffer: {e}")
            print("Cleaned up buffer resources")
            # Note: Images are NOT cleaned up here as they may be reused (same pattern as Bedrock)

