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




class OCIModel:
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
        self.model_id = "ocid1.generativeaimodel.oc1.us-chicago-1.amaaaaaask7dceyayjawvuonfkw2ua4bob4rlnnlhs522pafbglivtwlfzta"
        self.compartment_id = "ocid1.compartment.oc1..aaaaaaaa7wyo7euk2wfekpv36obtfbqgupxeb5yylivifscxseudvwwp2ixa"
        
        # Load configuration
        self.config = self._load_config()
        self.max_tokens = self.config.get("max_tokens", 4096)
        
        # Initialize client
        self.client = self._initialize_client(endpoint)
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load OCI configuration.
        
        Returns:
            dict: OCI configuration parameters
        """
        print("Loading OCI Generative AI configuration")
        return {
            "max_tokens": 4096,  # Default max tokens
            "timeout": (10, 240),  # (connect_timeout, read_timeout)
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
    
    def _encode_image_to_base64(self, pil_image: Image.Image) -> str:
        """
        Convert PIL image to base64 string.
        
        This follows the same pattern as BaseModel._encode_image_to_base64()
        in the codebase for consistency.
        
        Args:
            pil_image: PIL Image object
        
        Returns:
            str: Base64 encoded image string
        """
        buffer = BytesIO()
        try:
            pil_image.save(buffer, format="PNG")
            base64_str = base64.b64encode(buffer.getvalue()).decode()
            return base64_str
        finally:
            if buffer and not buffer.closed:
                buffer.close()
    
    def _extract_text_from_response(self, chat_response) -> str:
        """
        Extract text content from OCI chat response.
        
        Similar to BedrockModel._extract_text_from_response().
        
        Args:
            chat_response: OCI chat response object
        
        Returns:
            str: Extracted text content
        """
        try:
            response_data = chat_response.data
            
            # Handle if response_data is a JSON string (as seen in response_output.txt)
            if isinstance(response_data, str):
                try:
                    response_data = json.loads(response_data)
                except json.JSONDecodeError:
                    # If it's not valid JSON, return as-is
                    return response_data
            
            # Handle if response_data is a dict (from vars() or similar)
            if isinstance(response_data, dict):
                chat_response_data = response_data.get("chat_response", {})
            else:
                chat_response_data = response_data.chat_response if hasattr(response_data, 'chat_response') else response_data
            
            # Extract choices
            if isinstance(chat_response_data, dict):
                choices = chat_response_data.get("choices", [])
            else:
                choices = chat_response_data.choices if hasattr(chat_response_data, 'choices') else []
            
            if not choices:
                return ""
            
            # Get first choice
            first_choice = choices[0] if isinstance(choices, list) else choices
            
            # Extract message
            if isinstance(first_choice, dict):
                message = first_choice.get("message", {})
            else:
                message = first_choice.message if hasattr(first_choice, 'message') else {}
            
            # Extract content
            if isinstance(message, dict):
                content_list = message.get("content", [])
            else:
                content_list = message.content if hasattr(message, 'content') else []
            
            if not content_list:
                return ""
            
            # Get first content item
            first_content = content_list[0] if isinstance(content_list, list) else content_list
            
            # Extract text
            if isinstance(first_content, dict):
                text = first_content.get("text", "")
            else:
                text = first_content.text if hasattr(first_content, 'text') else ""
            
            return text if isinstance(text, str) else str(text)
            
        except Exception as e:
            print(f"Error extracting text from response: {e}")
            return ""
    
    def _clean_and_parse_json(self, text: str) -> Dict[str, Any]:
        """
        Clean and parse JSON response from LLAMA model.
        
        Removes markdown code blocks and parses JSON string.
        Similar to ExtractionService._clean_and_parse_json().
        
        Args:
            text: Raw text response from LLAMA (may contain markdown code blocks)
        
        Returns:
            dict: Parsed JSON object or error dict
        """
        if not text:
            return {"error": "Empty response from LLAMA model"}
        
        # Handle if text is a JSON string that needs parsing first
        try:
            # Try to parse as JSON string first (in case response.data is a JSON string)
            parsed = json.loads(text)
            if isinstance(parsed, dict) and "chat_response" in parsed:
                # Extract the actual text from nested structure
                text = self._extract_text_from_response(type('obj', (object,), {'data': parsed})())
        except (json.JSONDecodeError, AttributeError):
            # Not a JSON string, use text as-is
            pass
        
        # Clean response - remove markdown code blocks
        # Pattern matches: ```json\n at start and \n``` at end
        json_text = re.sub(r"^```json\s*\n|\n\s*```$", "", text, flags=re.MULTILINE).strip()
        
        # Also handle cases where there might be just ``` without json
        json_text = re.sub(r"^```\s*\n|\n\s*```$", "", json_text, flags=re.MULTILINE).strip()
        
        # Validate content
        if not json_text:
            print("LLAMA returned empty response after cleaning")
            return {"error": "LLAMA extraction failed: Empty response after processing"}
        
        # Parse JSON
        try:
            cleaned_json = json.loads(json_text)
            return {"cleaned_json": cleaned_json}
        except json.JSONDecodeError as e:
            print(f"Failed to parse LLAMA response as JSON: {e}")
            preview = json_text
            print(f"Raw response preview: {preview}...")
            return {"error": f"LLAMA extraction failed: Invalid JSON response - {str(e)}"}
    
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
                usage = response_data.chat_response.usage if hasattr(response_data, 'chat_response') and hasattr(response_data.chat_response, 'usage') else {}
            
            if usage:
                token_usage = {
                    "prompt_tokens": usage.get("prompt_tokens") if isinstance(usage, dict) else getattr(usage, 'prompt_tokens', None),
                    "completion_tokens": usage.get("completion_tokens") if isinstance(usage, dict) else getattr(usage, 'completion_tokens', None),
                    "total_tokens": usage.get("total_tokens") if isinstance(usage, dict) else getattr(usage, 'total_tokens', None),
                }
        except Exception as e:
            print(f"Could not extract token usage: {e}")
        
        return {
            "data": parse_result["cleaned_json"],  # Return parsed JSON object, not string
            "token_usage": token_usage,
            "response_time_seconds": round(end_time - start_time, 2),
        }

    def infer_with_images(
        self,
        images: List[Image.Image],
        prompt: str,
        max_tokens: int = None,
        temperature: float = 1,
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
                    # image_content.type = 'IMAGE'
                    given_image_url = oci.generative_ai_inference.models.ImageUrl()
                    given_image_url.url =  f"data:image/png;base64,{image_base64}"  # base64 string (SDK converts to bytes)

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

            try:
                return self._format_oci_response(
                    chat_response, start_time, end_time, validate_empty=True
                )
                
            except Exception as e:
                print(f"Error formatting response: {e}")
                return {
                    "data": str(chat_response),
                    "response_time_seconds": end_time - start_time,
                    "full_response": vars(chat_response)
                }
        
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




