import aiohttp
import logging
import re
import os
from typing import Dict, Any, Optional
from dealcloud_sdk import DealCloud
from pydantic.v1 import BaseModel, ValidationError, Field, validator
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, before_sleep_log
from integrations.base import BaseIntegration

logger = logging.getLogger(__name__)

class DealCloudError(Exception):
    """Base exception class for DealCloud errors"""
    pass

class DealCloudRateLimitError(DealCloudError):
    """Raised when API rate limit is exceeded"""
    pass

class DealCloudTimeoutError(DealCloudError):
    """Raised when API request times out"""
    pass

def log_execution(retry_state):
    """Log retry attempts for tenacity"""
    logger.warning(f"Retrying {retry_state.fn}: attempt {retry_state.attempt_number}")

class DealCloudConfig(BaseModel):
    """DealCloud API configuration"""
    client_id: str = Field(..., env="DC_SDK_CLIENT_ID")
    client_secret: str = Field(..., env="DC_SDK_CLIENT_SECRET")
    site_url: str = Field(..., env="DC_SDK_SITE_URL")
    max_retries: int = Field(3, env="DEALCLOUD_MAX_RETRIES")
    timeout: int = Field(30, env="DEALCLOUD_TIMEOUT")

    @classmethod
    def from_env(cls):
        """Load configuration from environment variables with validation"""
        return cls(
            client_id=os.getenv("DC_SDK_CLIENT_ID"),
            client_secret=os.getenv("DC_SDK_CLIENT_SECRET"),
            site_url=os.getenv("DC_SDK_SITE_URL"),
            max_retries=int(os.getenv("DEALCLOUD_MAX_RETRIES", 3)),
            timeout=int(os.getenv("DEALCLOUD_TIMEOUT", 30))
        )

    @validator('client_id', 'client_secret', 'site_url')
    def validate_required_fields(cls, value):
        if not value:
            raise ValueError("Missing required DealCloud environment variable")
        return value

class DealCloudClient(BaseIntegration):
    """Client for interacting with DealCloud API"""
    
    def __init__(self, config: DealCloudConfig):
        super().__init__(config)
        self.session: Optional[aiohttp.ClientSession] = None
        self.sdk: Optional[DealCloud] = None

    async def initialize_sdk(self):
        """Initialize the DealCloud SDK with validated configuration"""
        if self.sdk and self.sdk.authenticated:
            return  # Already initialized

        try:
            # Load config first
            config = DealCloudConfig.from_env()
            
            # Initialize SDK with validated config
            self.sdk = DealCloud(
                client_id=config.client_id,
                client_secret=config.client_secret,
                site_url=config.site_url
            )
            
            # Perform async authentication
            await self.sdk.authenticate()
            
        except ValidationError as e:
            logger.error("Configuration validation failed", exc_info=True)
            raise DealCloudError(f"Invalid DealCloud configuration: {e.errors()}") from e
        except aiohttp.ClientError as e:
            logger.error("Network error during authentication", exc_info=True)
            raise DealCloudError(f"Connection failed: {str(e)}") from e
        except Exception as e:
            logger.error("Authentication failed", exc_info=True)
            raise DealCloudError("Authentication failed - check credentials and network") from e
        
    def get_headers(self) -> Dict[str, str]:
        """Get authentication headers from SDK"""
        if not self.sdk or not self.sdk.is_authenticated():
            raise DealCloudError("SDK not authenticated - call initialize_sdk first")
            
        return {
            "Authorization": f"Bearer {self.sdk.token}",
            "Content-Type": "application/json"
        }

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((DealCloudRateLimitError, DealCloudTimeoutError)),
        before_sleep=log_execution
    )
    async def make_request(self, endpoint: str, method: str = "POST", data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make an async HTTP request with retry logic"""
        url = f"{self.config.base_url}/{endpoint.lstrip('/')}"
        headers = self.get_headers()
        
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.request(method, url, json=data, headers=headers) as response:
                logger.info(f"Making request to: {url}")
                
                if response.status == 429:
                    raise DealCloudRateLimitError("Rate limit exceeded")
                if response.status == 504:
                    raise DealCloudTimeoutError("Request timed out")
                
                response.raise_for_status()
                return await response.json()
                
        except aiohttp.ClientError as e:
            logger.error(f"Request failed: {str(e)}")
            raise
