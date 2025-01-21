import asyncio
import os
import pytest
import logging
from dotenv import load_dotenv
from datetime import datetime
from integrations.dealcloud.client import DealCloudClient, DealCloudConfig

# Load environment variables from .env file
load_dotenv()

@pytest.mark.asyncio
@pytest.mark.timeout(120)  # Increased timeout for real API operations
async def test_interaction_workflow(caplog):
    """End-to-end test for DealCloud interaction lifecycle"""
    # Configure debug logging with async support
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # Check for required SDK environment variables
    required_vars = ["DC_SDK_SITE_URL", "DC_SDK_CLIENT_ID", "DC_SDK_CLIENT_SECRET"]
    if not all(os.getenv(v) for v in required_vars):
        pytest.skip("DealCloud environment variables not configured")

    # Initialize client with async SDK setup
    client = DealCloudClient(DealCloudConfig.from_env())
    
    # Initialize SDK with timeout
    try:
            # Initialize SDK synchronously
            await client.initialize_sdk()
    except asyncio.TimeoutError as e:
        pytest.fail(f"SDK initialization timed out: {str(e)}")
    
    # Create test interaction data
    interaction_data = {
        "Date": datetime.now().isoformat(),
        "Subject": "Phone Call with Yvo de Rooij",
        "Type": "Phone Call Summary",
        "Notes": "Discussed CRM integration requirements and implementation timeline",
        "Participants": ["Yvo de Rooij"],
        "Status": "Completed"
    }

    try:
        # Create interaction with extended timeout and diagnostics
        start_time = datetime.now()
        logger.info(f"Starting interaction creation at {start_time.isoformat()}")
        
        try:
            result = await client.insert_data("Interaction", [interaction_data])
            created_id = result[0]['EntryId']
            duration = (datetime.now() - start_time).total_seconds()
            caplog.info(f"Successfully created interaction ID: {created_id} in {duration:.2f}s")
            
            # Immediate sanity check
            if not isinstance(created_id, int):
                pytest.fail(f"Unexpected EntryId format: {type(created_id)} {created_id}")
                
        except Exception as e:
            caplog.error(f"Interaction creation failed after {(datetime.now() - start_time).total_seconds():.2f}s: {str(e)}")
            raise

        # Verify creation with timeout
        verification = await client.read_data("Interaction", query=f"EntryId: {created_id}")
        assert len(verification) == 1, "Interaction not found after creation"
        assert verification[0]['Notes'] == interaction_data['Notes']
        caplog.info(f"Verification successful at {datetime.now().isoformat()} - interaction exists with correct notes")

        # Update interaction with timeout
        update_data = {"EntryId": created_id, "Notes": "Updated notes with action items"}
        client.update_data("Interaction", [update_data])
        caplog.info(f"Update completed at {datetime.now().isoformat()}")
        
        # Verify update with timeout
        updated = await asyncio.wait_for(
            client.read_data("Interaction", query=f"EntryId: {created_id}"),
            timeout=30
        )
        assert updated[0]['Notes'] == "Updated notes with action items"
        caplog.info(f"Update verification successful at {datetime.now().isoformat()}")

    finally:
        # Cleanup with timeout and diagnostics
        if 'created_id' in locals() and not os.getenv("PRESERVE_TEST_DATA"):
            try:
                start_time = datetime.now()
                caplog.info(f"Starting cleanup of interaction {created_id} at {start_time.isoformat()}")
                
                await asyncio.wait_for(
                    client.delete_data("Interaction", [created_id]),
                    timeout=30
                )
                duration = (datetime.now() - start_time).total_seconds()
                caplog.info(f"Successfully cleaned up interaction {created_id} in {duration:.2f}s")
                
            except Exception as e:
                caplog.error(f"Cleanup failed after {(datetime.now() - start_time).total_seconds():.2f}s: {str(e)}")
                raise

if __name__ == "__main__":
    pytest.main(["-v", __file__])
