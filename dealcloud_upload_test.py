from dealcloud_sdk import DealCloud
from dotenv import load_dotenv
from datetime import datetime
import os
import logging
from utils.logging import log_execution

logger = logging.getLogger(__name__)

@log_execution()
def create_test_interaction():
    """Create a test interaction in DealCloud CRM"""
    load_dotenv()
    
    try:
        logger.info("Starting DealCloud integration test")
        
        # Explicitly get and validate environment variables
        site_url = os.getenv("DC_SDK_SITE_URL")
        client_id = os.getenv("DC_SDK_CLIENT_ID")
        client_secret = os.getenv("DC_SDK_CLIENT_SECRET")
        
        print(f"Site URL: {site_url}")
        print(f"Client ID: {client_id}")
        print(f"Client Secret: {'*' * len(client_secret) if client_secret else 'None'}")
        
        if not all([site_url, client_id, client_secret]):
            missing = [k for k, v in [
                ("DC_SDK_SITE_URL", site_url),
                ("DC_SDK_CLIENT_ID", client_id),
                ("DC_SDK_CLIENT_SECRET", client_secret)
            ] if not v]
            logger.error(f"Missing required environment variables: {', '.join(missing)}")
            return False
            
        logger.debug(f"Using DealCloud site: {site_url}")
            
        dc = DealCloud(
            site_url=site_url,
            client_id=client_id,
            client_secret=client_secret
        )
        logger.info("Successfully initialized DealCloud client")

        # Get first available company
        logger.info("Fetching companies...")
        # Try to get companies without a query first
        companies = dc.read_data("Company", output="list")
        if not companies:
            logger.error("No companies found")
            return False
        company_id = companies[0]["EntryId"]
        logger.info(f"Using company ID: {company_id}")

        # Try to get existing interactions to understand the data format
        logger.info("Fetching sample interactions...")
        existing = dc.read_data("Interaction", output="list")
        if existing:
            logger.info(f"Found existing interaction format: {existing[0]}")
            type_id = existing[0].get("Type", 1)  # Use existing type ID or fallback to 1
            date_format = existing[0].get("Date")  # See how dates are formatted
            logger.info(f"Using type_id: {type_id}, date format example: {date_format}")
        else:
            logger.info("No existing interactions found, using defaults")
            type_id = 1
            date_format = None

        # Create interaction data with simple field values
        interaction_data = [{
            "Date": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),  # ISO 8601 format
            "Subject": "Test Phone Call",
            "Notes": "Test interaction created via DealCloud SDK",
            "InternalAttendees": int(client_id),  # Just the ID
            "Companies": company_id,  # Just the ID
            "Type": 1947215  # Just the ID from example
        }]
        
        logger.info(f"Creating interaction with data: {interaction_data}")
        
        response = dc.insert_data(
            object_api_name="Interaction",
            data=interaction_data
        )
        
        if response and isinstance(response, list) and response[0].get('EntryId'):
            logger.info(f"Successfully created interaction ID: {response[0]['EntryId']}")
            logger.debug(f"Full response: {response}")
            return True
        else:
            logger.error("Failed to create interaction")
            logger.debug(f"API response: {response}")
            return False
        
    except Exception as e:
        logger.critical(f"Failed to create interaction: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    create_test_interaction()
