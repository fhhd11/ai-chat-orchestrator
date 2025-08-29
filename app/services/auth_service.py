"""Authentication service for JWT token validation"""

from typing import Dict, Optional
from jose import jwt, JWTError
from cachetools import TTLCache
from loguru import logger

from ..config import Settings
from ..utils.errors import (
    AuthenticationError, 
    TokenExpiredError, 
    InvalidTokenError
)


class AuthService:
    """Service for handling JWT authentication"""
    
    def __init__(self, settings: Settings):
        self.jwt_secret_key = settings.jwt_secret_key
        self.jwt_algorithm = settings.jwt_algorithm
        self.cache = TTLCache(maxsize=1000, ttl=300)  # 5 minutes TTL
    
    def decode_jwt(self, token: str) -> Dict[str, any]:
        """
        Decode and validate JWT token
        
        Args:
            token: JWT token string (without 'Bearer ' prefix)
            
        Returns:
            Decoded token payload
            
        Raises:
            TokenExpiredError: If token is expired
            InvalidTokenError: If token is invalid
            AuthenticationError: If token cannot be decoded
        """
        # Check cache first
        if token in self.cache:
            logger.debug("Token found in cache")
            return self.cache[token]
        
        try:
            # Decode token
            payload = jwt.decode(
                token,
                self.jwt_secret_key,
                algorithms=[self.jwt_algorithm],
                audience="authenticated"
            )
            
            # Validate required fields
            if not payload.get("sub"):
                raise InvalidTokenError(
                    message="Token missing subject (user ID)",
                    code="MISSING_SUBJECT"
                )
            
            if not payload.get("exp"):
                raise InvalidTokenError(
                    message="Token missing expiration",
                    code="MISSING_EXPIRATION"
                )
            
            # Cache valid token
            self.cache[token] = payload
            logger.debug(f"Token validated for user: {payload.get('sub')}")
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            raise TokenExpiredError(
                message="Token has expired",
                code="TOKEN_EXPIRED"
            )
            
        except jwt.JWTClaimsError as e:
            logger.warning(f"JWT claims error: {e}")
            raise InvalidTokenError(
                message=f"Invalid token claims: {str(e)}",
                code="INVALID_CLAIMS"
            )
            
        except jwt.JWTError as e:
            logger.warning(f"JWT decode error: {e}")
            raise InvalidTokenError(
                message=f"Invalid token: {str(e)}",
                code="INVALID_TOKEN"
            )
            
        except Exception as e:
            logger.error(f"Unexpected error decoding JWT: {e}")
            raise AuthenticationError(
                message=f"Authentication error: {str(e)}",
                code="AUTH_ERROR"
            )
    
    def extract_bearer_token(self, authorization: str) -> str:
        """
        Extract JWT token from Authorization header
        
        Args:
            authorization: Authorization header value
            
        Returns:
            JWT token string
            
        Raises:
            InvalidTokenError: If header format is invalid
        """
        if not authorization:
            raise InvalidTokenError(
                message="Missing Authorization header",
                code="MISSING_AUTH_HEADER"
            )
        
        if not authorization.startswith("Bearer "):
            raise InvalidTokenError(
                message="Invalid Authorization header format. Expected 'Bearer <token>'",
                code="INVALID_AUTH_FORMAT"
            )
        
        token = authorization[7:]  # Remove "Bearer " prefix
        
        if not token:
            raise InvalidTokenError(
                message="Empty token in Authorization header",
                code="EMPTY_TOKEN"
            )
        
        return token
    
    def get_user_id_from_token(self, authorization: str) -> str:
        """
        Extract user ID from Authorization header
        
        Args:
            authorization: Authorization header value
            
        Returns:
            User ID string
            
        Raises:
            AuthenticationError: If token is invalid or missing user ID
        """
        token = self.extract_bearer_token(authorization)
        payload = self.decode_jwt(token)
        return payload["sub"]
    
    def validate_token_and_get_user(self, authorization: str) -> Dict[str, any]:
        """
        Validate token and return user info
        
        Args:
            authorization: Authorization header value
            
        Returns:
            Token payload with user info
            
        Raises:
            AuthenticationError: If token is invalid
        """
        token = self.extract_bearer_token(authorization)
        return self.decode_jwt(token)
    
    def clear_cache(self):
        """Clear the token cache"""
        self.cache.clear()
        logger.info("Token cache cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            "size": len(self.cache),
            "maxsize": self.cache.maxsize,
            "ttl": self.cache.ttl,
            "hits": getattr(self.cache, 'hits', 0),
            "misses": getattr(self.cache, 'misses', 0)
        }