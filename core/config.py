from typing import Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field, EmailStr
from .types import IndustryType, CompanyStage

class FundCriteria(BaseModel):
    """Criteria for fund investment decisions."""
    min_revenue: float
    target_industries: List[IndustryType]
    stages: List[CompanyStage]
    check_size: tuple[float, float]
    required_growth_rate: Optional[float] = None

class SlackConfig(BaseModel):
    """Slack integration configuration."""
    bot_token: str
    app_token: str
    source_channel: str
    follow_up_channel: str
    fund_x_channel: str
    no_action_channel: str

class DealCloudConfig(BaseModel):
    """DealCloud integration configuration."""
    api_key: str
    base_url: str
    workspace_id: str

class OpenAIConfig(BaseModel):
    """OpenAI configuration."""
    api_key: str
    model: str = "gpt-4o"
    temperature: float = 0.0

class EmailProvider(str, Enum):
    """Supported email providers."""
    GMAIL = "gmail"
    OFFICE365 = "office365"

class EmailConfig(BaseModel):
    """Email configuration."""
    provider: EmailProvider = Field(..., description="Email provider (gmail or office365)")
    username: str = Field(..., description="Email username/address")
    password: str = Field(..., description="Email password or app-specific password")
    from_email: EmailStr = Field(..., description="Email address to send from")
    gesprekseigenaar_email: EmailStr = Field(..., description="Email address of conversation owner")
    cc_recipients: Optional[List[EmailStr]] = Field(None, description="Optional CC recipients")
    bcc_recipients: Optional[List[EmailStr]] = Field(None, description="Optional BCC recipients")

    class Config:
        use_enum_values = True

class AppConfig(BaseModel):
    """Main application configuration."""
    # Authentication and API keys
    slack: SlackConfig
    dealcloud: Optional[DealCloudConfig] = None
    openai: OpenAIConfig
    email: EmailConfig
    
    # Fund criteria
    fund_criteria: Dict[str, FundCriteria]
    
    # Processing settings
    log_level: str = "INFO"
    min_confidence_threshold: float = 0.7
    max_processing_time: int = 300  # seconds
    
    # Feature flags
    enable_dealcloud: bool = True
    enable_socket_mode: bool = True
    
    class Config:
        """Pydantic config"""
        use_enum_values = True
