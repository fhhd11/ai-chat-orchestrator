"""Custom Pydantic validators and validation utilities"""

import re
import uuid
from typing import Any, Optional, List, Dict, Union
from datetime import datetime, timezone
from pydantic import validator, ValidationError
from email_validator import validate_email, EmailNotValidError


class ValidationUtils:
    """Utility class for common validation functions"""
    
    @staticmethod
    def is_valid_uuid(value: str) -> bool:
        """Check if string is a valid UUID"""
        try:
            uuid.UUID(value)
            return True
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Check if string is a valid email"""
        try:
            validate_email(email)
            return True
        except EmailNotValidError:
            return False
    
    @staticmethod
    def validate_model_name(model: str) -> bool:
        """Validate LLM model name format"""
        # Common patterns for model names
        patterns = [
            r'^gpt-[34](\.\d+)?(-turbo)?(-\d+k)?$',  # OpenAI GPT models
            r'^claude-[123](\.\d+)?(-haiku|-sonnet|-opus)?$',  # Anthropic Claude
            r'^gemini-(pro|ultra)(-vision)?$',  # Google Gemini
            r'^llama-?\d+b?(-chat|-instruct)?$',  # Meta LLaMA
            r'^mistral-(tiny|small|medium|large)$',  # Mistral
            r'^text-davinci-\d+$',  # Legacy OpenAI models
            r'^[a-zA-Z0-9][a-zA-Z0-9-_\.]*[a-zA-Z0-9]$'  # Generic format
        ]
        
        return any(re.match(pattern, model, re.IGNORECASE) for pattern in patterns)
    
    @staticmethod
    def sanitize_text(text: str, max_length: Optional[int] = None) -> str:
        """Sanitize text input"""
        # Remove null bytes and control characters except newlines
        sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Limit length if specified
        if max_length and len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized.strip()
    
    @staticmethod
    def validate_json_object(value: Any) -> Dict[str, Any]:
        """Validate that value is a valid JSON object"""
        if isinstance(value, str):
            try:
                import json
                parsed = json.loads(value)
                if not isinstance(parsed, dict):
                    raise ValueError("Must be a JSON object")
                return parsed
            except (json.JSONDecodeError, ValueError) as e:
                raise ValueError(f"Invalid JSON: {e}")
        elif isinstance(value, dict):
            return value
        else:
            raise ValueError("Must be a JSON object or string")


def validate_uuid_field(cls, v: str) -> str:
    """Pydantic validator for UUID fields"""
    if not ValidationUtils.is_valid_uuid(v):
        raise ValueError("Invalid UUID format")
    return v


def validate_email_field(cls, v: str) -> str:
    """Pydantic validator for email fields"""
    if not ValidationUtils.is_valid_email(v):
        raise ValueError("Invalid email format")
    return v.lower()


def validate_model_field(cls, v: Optional[str]) -> Optional[str]:
    """Pydantic validator for model name fields"""
    if v is None:
        return v
    
    v = v.strip()
    if not v:
        return None
    
    if not ValidationUtils.validate_model_name(v):
        raise ValueError(f"Invalid model name format: {v}")
    
    return v


def validate_positive_number(cls, v: Union[int, float]) -> Union[int, float]:
    """Pydantic validator for positive numbers"""
    if v is not None and v < 0:
        raise ValueError("Must be a positive number")
    return v


def validate_temperature(cls, v: Optional[float]) -> Optional[float]:
    """Pydantic validator for temperature parameter"""
    if v is not None:
        if not 0 <= v <= 2:
            raise ValueError("Temperature must be between 0 and 2")
    return v


def validate_max_tokens(cls, v: Optional[int]) -> Optional[int]:
    """Pydantic validator for max_tokens parameter"""
    if v is not None:
        if not 1 <= v <= 32000:
            raise ValueError("Max tokens must be between 1 and 32000")
    return v


def validate_page_size(cls, v: int) -> int:
    """Pydantic validator for pagination page size"""
    if not 1 <= v <= 100:
        raise ValueError("Page size must be between 1 and 100")
    return v


def validate_search_query(cls, v: Optional[str]) -> Optional[str]:
    """Pydantic validator for search queries"""
    if v is None:
        return v
    
    # Sanitize and validate search query
    sanitized = ValidationUtils.sanitize_text(v, max_length=200)
    
    if len(sanitized) < 1:
        raise ValueError("Search query must be at least 1 character")
    
    # Check for SQL injection patterns (basic)
    dangerous_patterns = [
        r";\s*(drop|delete|update|insert|create|alter|exec|execute)",
        r"(union|select).*from",
        r"(script|javascript|vbscript):",
        r"<.*script.*>",
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, sanitized, re.IGNORECASE):
            raise ValueError("Search query contains invalid characters")
    
    return sanitized


def validate_conversation_title(cls, v: Optional[str]) -> Optional[str]:
    """Pydantic validator for conversation titles"""
    if v is None:
        return v
    
    sanitized = ValidationUtils.sanitize_text(v, max_length=200)
    
    if not sanitized:
        return None
    
    return sanitized


def validate_message_content(cls, v: str) -> str:
    """Pydantic validator for message content"""
    if not v or not v.strip():
        raise ValueError("Message content cannot be empty")
    
    sanitized = ValidationUtils.sanitize_text(v, max_length=32000)
    
    if len(sanitized) < 1:
        raise ValueError("Message content cannot be empty after sanitization")
    
    return sanitized


def validate_iso_datetime(cls, v: Optional[str]) -> Optional[datetime]:
    """Pydantic validator for ISO datetime strings"""
    if v is None:
        return v
    
    try:
        # Parse ISO format datetime
        dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
        
        # Ensure timezone awareness
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        return dt
    except ValueError:
        raise ValueError("Invalid ISO datetime format")


def validate_language_code(cls, v: str) -> str:
    """Pydantic validator for language codes"""
    # Simple validation for common language codes
    if not re.match(r'^[a-z]{2}(-[A-Z]{2})?$', v):
        raise ValueError("Invalid language code format")
    return v.lower()


def validate_timezone(cls, v: Optional[str]) -> Optional[str]:
    """Pydantic validator for timezone strings"""
    if v is None:
        return v
    
    # Basic timezone validation
    try:
        import zoneinfo
        zoneinfo.ZoneInfo(v)
        return v
    except Exception:
        # Fallback for systems without zoneinfo
        common_timezones = [
            'UTC', 'GMT', 'US/Eastern', 'US/Central', 'US/Mountain', 'US/Pacific',
            'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'Europe/Moscow',
            'Asia/Tokyo', 'Asia/Shanghai', 'Asia/Kolkata', 'Australia/Sydney'
        ]
        
        if v not in common_timezones:
            raise ValueError(f"Unsupported timezone: {v}")
        
        return v


def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
    """Pydantic validator for phone numbers"""
    if v is None:
        return v
    
    # Remove all non-digit characters
    cleaned = re.sub(r'[^\d+]', '', v)
    
    # Basic international phone number validation
    if not re.match(r'^\+?[1-9]\d{1,14}$', cleaned):
        raise ValueError("Invalid phone number format")
    
    return cleaned


def validate_url(cls, v: Optional[str]) -> Optional[str]:
    """Pydantic validator for URLs"""
    if v is None:
        return v
    
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    if not url_pattern.match(v):
        raise ValueError("Invalid URL format")
    
    return v


def validate_json_metadata(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Pydantic validator for metadata JSON fields"""
    if v is None:
        return v
    
    # Validate size (serialized)
    import json
    serialized = json.dumps(v)
    if len(serialized) > 10000:  # 10KB limit
        raise ValueError("Metadata too large (max 10KB)")
    
    # Check for dangerous content
    def check_safe_value(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if not isinstance(key, str):
                    raise ValueError("Metadata keys must be strings")
                check_safe_value(value)
        elif isinstance(obj, list):
            for item in obj:
                check_safe_value(item)
        elif isinstance(obj, str):
            # Check for script injection
            if re.search(r'<.*?script.*?>', obj, re.IGNORECASE):
                raise ValueError("Metadata contains unsafe content")
    
    check_safe_value(v)
    return v


class PaginationValidator:
    """Validator class for pagination parameters"""
    
    @staticmethod
    def validate_page(page: int) -> int:
        """Validate page number"""
        if page < 1:
            raise ValueError("Page number must be at least 1")
        if page > 10000:  # Reasonable upper limit
            raise ValueError("Page number too large")
        return page
    
    @staticmethod
    def validate_limit(limit: int, max_limit: int = 100) -> int:
        """Validate page size limit"""
        if limit < 1:
            raise ValueError("Limit must be at least 1")
        if limit > max_limit:
            raise ValueError(f"Limit cannot exceed {max_limit}")
        return limit
    
    @staticmethod
    def validate_sort_field(field: str, allowed_fields: List[str]) -> str:
        """Validate sort field"""
        if field not in allowed_fields:
            raise ValueError(f"Invalid sort field. Allowed: {', '.join(allowed_fields)}")
        return field
    
    @staticmethod
    def validate_sort_order(order: str) -> str:
        """Validate sort order"""
        order = order.lower()
        if order not in ['asc', 'desc']:
            raise ValueError("Sort order must be 'asc' or 'desc'")
        return order