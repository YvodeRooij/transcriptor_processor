from abc import ABC, abstractmethod
import requests
from typing import Dict, Any

class BaseIntegration(ABC):
    def __init__(self, base_url: str):
        self.base_url = base_url

    @abstractmethod
    def get_headers(self) -> Dict[str, str]:
        pass

    def make_request(self, endpoint: str, method: str = "POST", data: Dict[str, Any] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self.get_headers()
        
        response = requests.request(method, url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()
