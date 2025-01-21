import pytest
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import ClientSession, ClientResponse
from integrations.dealcloud.client import DealCloudClient

logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_create_deal():
    # Mock response
    mock_response = AsyncMock(spec=ClientResponse)
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"deal_id": "123"})
    mock_response.raise_for_status = MagicMock()

    # Mock client session
    mock_session = AsyncMock(spec=ClientSession)
    mock_session.request.return_value.__aenter__.return_value = mock_response

    # Test data with all fields that would come from urgent button
    deal_data = {
        "deal_type": "urgent",
        "company": "Test Company",
        "timestamp": "2024-01-01T00:00:00Z"
    }
    custom_base_url = "https://custom.dealcloud.com"

    with patch('aiohttp.ClientSession', return_value=mock_session):
        client = DealCloudClient(
            api_key="dummy",
            tenant="dummy_tenant",
            base_url=custom_base_url
        )
        result = await client.create_deal(deal_data)
        
        # Verify result
        # Verify full response matches what we expect from urgent button press
        assert result == {"deal_id": "123"}
        logger.info(f"✅ Successfully tested deal creation with data: {deal_data}")
        
        # Verify request was made correctly with custom base URL
        mock_session.request.assert_called_once_with(
            "POST",
            f"{custom_base_url}/deals",
            json=deal_data,
            headers={
                'Authorization': 'Bearer dummy',
                'X-Tenant': 'dummy_tenant',
                'Content-Type': 'application/json'
            }
        )

    # Test with default base URL
    with patch('aiohttp.ClientSession', return_value=mock_session):
        client = DealCloudClient(api_key="dummy", tenant="dummy_tenant")
        result = await client.create_deal(deal_data)
        
        # Verify request was made correctly with default base URL
        assert mock_session.request.call_args_list[-1] == (
            (),
            {
                'method': "POST",
                'url': "https://api.dealcloud.com/deals",
                'json': deal_data,
                'headers': {
                    'Authorization': 'Bearer dummy',
                    'X-Tenant': 'dummy_tenant',
                    'Content-Type': 'application/json'
                }
            }
        )

@pytest.mark.asyncio
async def test_update_deal():
    # Mock response
    mock_response = AsyncMock(spec=ClientResponse)
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"updated": True})
    mock_response.raise_for_status = MagicMock()

    # Mock client session
    mock_session = AsyncMock(spec=ClientSession)
    mock_session.request.return_value.__aenter__.return_value = mock_response

    # Test data
    deal_id = "123"
    update_data = {"status": "updated"}
    custom_base_url = "https://custom.dealcloud.com"

    with patch('aiohttp.ClientSession', return_value=mock_session):
        client = DealCloudClient(
            api_key="dummy",
            tenant="dummy_tenant",
            base_url=custom_base_url
        )
        result = await client.update_deal(deal_id, update_data)
        
        # Verify result
        assert result == {"updated": True}
        
        # Verify request was made correctly with custom base URL
        mock_session.request.assert_called_once_with(
            "PATCH",
            f"{custom_base_url}/deals/{deal_id}",
            json=update_data,
            headers={
                'Authorization': 'Bearer dummy',
                'X-Tenant': 'dummy_tenant',
                'Content-Type': 'application/json'
            }
        )

    # Test with default base URL
    with patch('aiohttp.ClientSession', return_value=mock_session):
        client = DealCloudClient(api_key="dummy", tenant="dummy_tenant")
        result = await client.update_deal(deal_id, update_data)
        
        # Verify request was made correctly with default base URL
        assert mock_session.request.call_args_list[-1] == (
            (),
            {
                'method': "PATCH",
                'url': f"https://api.dealcloud.com/deals/{deal_id}",
                'json': update_data,
                'headers': {
                    'Authorization': 'Bearer dummy',
                    'X-Tenant': 'dummy_tenant',
                    'Content-Type': 'application/json'
                }
            }
        )

@pytest.mark.asyncio
async def test_error_handling():
    # Mock error response
    mock_response = AsyncMock(spec=ClientResponse)
    mock_response.status = 400
    mock_response.raise_for_status = MagicMock(side_effect=Exception("API Error"))

    # Mock client session
    mock_session = AsyncMock(spec=ClientSession)
    mock_session.request.return_value.__aenter__.return_value = mock_response

    with patch('aiohttp.ClientSession', return_value=mock_session):
        client = DealCloudClient(api_key="dummy", tenant="dummy_tenant")
        
        # Test error handling
        with pytest.raises(Exception) as exc_info:
            await client.create_deal({"test": "data"})
        assert str(exc_info.value) == "API Error"
