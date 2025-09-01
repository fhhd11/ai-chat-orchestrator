# Legacy alias for backward compatibility
from .litellm_client import LiteLLMService as LiteLLMServiceImpl

# Export the service
LiteLLMService = LiteLLMServiceImpl