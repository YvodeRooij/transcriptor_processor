import aiohttp
import logging
import re
import os
from datetime import datetime
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

class DealCloudClient(BaseIntegration):
    """Client for interacting with DealCloud API"""
    
    def __init__(self):
        """Initialize DealCloud client"""
        super().__init__(base_url=os.getenv("DC_SDK_SITE_URL", ""))
        self.dc = None
        self.client_id = None

    async def initialize(self):
        """Initialize DealCloud SDK with environment variables"""
        try:
            # Get environment variables exactly like in test
            site_url = os.getenv("DC_SDK_SITE_URL")
            client_id = os.getenv("DC_SDK_CLIENT_ID")
            client_secret = os.getenv("DC_SDK_CLIENT_SECRET")
            
            logger.debug(f"Using DealCloud site: {site_url}")
            
            if not all([site_url, client_id, client_secret]):
                missing = [k for k, v in [
                    ("DC_SDK_SITE_URL", site_url),
                    ("DC_SDK_CLIENT_ID", client_id),
                    ("DC_SDK_CLIENT_SECRET", client_secret)
                ] if not v]
                logger.error(f"Missing required environment variables: {', '.join(missing)}")
                raise DealCloudError("Missing required DealCloud credentials")

            # Initialize SDK exactly like in test
            self.dc = DealCloud(
                site_url=site_url,
                client_id=client_id,
                client_secret=client_secret
            )
            self.client_id = client_id
            logger.info("Successfully initialized DealCloud SDK")

        except Exception as e:
            logger.error("Failed to initialize DealCloud SDK", exc_info=True)
            raise DealCloudError(f"SDK initialization failed: {str(e)}") from e

    async def create_deal(self, deal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new interaction in DealCloud"""
        if not self.dc:
            await self.initialize()

        try:
            # Convert "Type" to an integer if it's passed as a list or dict
            type_val = deal_data.get("Type", 1947215)
            if isinstance(type_val, list) and type_val:
                # If it's a list, try first element's "id"
                first_item = type_val[0]
                deal_data["Type"] = first_item.get("id", 1947215)
            elif isinstance(type_val, dict):
                # If it's a dict, try "id"
                deal_data["Type"] = type_val.get("id", 1947215)
            else:
                # Default if it's missing or invalid
                deal_data["Type"] = type_val if isinstance(type_val, int) else 1947215

            # Get first available company
            logger.info("Fetching companies...")
            companies = self.dc.read_data("Company", output="list")
            if not companies:
                logger.error("No companies found")
                raise DealCloudError("No companies found")
            company_id = companies[0]["EntryId"]
            logger.info(f"Using company ID: {company_id}")

            # Try to get existing interactions to understand the data format
            logger.info("Fetching sample interactions...")
            existing = self.dc.read_data("Interaction", output="list")
            if existing:
                logger.info(f"Found existing interaction format: {existing[0]}")
                type_id = existing[0].get("Type", 1947215)  # Use existing type ID or fallback
                logger.info(f"Using type_id: {type_id}")
            else:
                logger.info("No existing interactions found, using default type_id")
                type_id = 1947215

            # Create interaction data
            interaction_data = [{
                "Date": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),  # ISO 8601 format
                "Subject": deal_data.get("Subject", "Meeting Follow-up"),
                "Notes": deal_data.get("Notes", ""),
                "InternalAttendees": int(self.client_id),
                "Companies": company_id,
                "Type": deal_data["Type"]
            }]
            
            logger.info(f"Creating interaction with data: {interaction_data}")
            
            # Create interaction exactly like in test
            response = self.dc.insert_data(
                object_api_name="Interaction",
                data=interaction_data
            )
            
            if response and isinstance(response, list) and response[0].get('EntryId'):
                logger.info(f"Successfully created interaction ID: {response[0]['EntryId']}")
                logger.debug(f"Full response: {response}")
                return response[0]
            else:
                logger.error("Failed to create interaction")
                logger.debug(f"API response: {response}")
                raise DealCloudError("Failed to create interaction")

        except Exception as e:
            logger.error(f"Failed to create interaction: {str(e)}", exc_info=True)
            raise DealCloudError(f"Failed to create interaction: {str(e)}") from e

    def get_headers(self) -> Dict[str, str]:
        """Return default or custom headers for requests."""
        return {}

    async def close(self):
        """Clean up resources"""
        self.dc = None
