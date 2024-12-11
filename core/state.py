from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from .types import DecisionType, IndustryType, CompanyStage

class Participant(BaseModel):
    """Represents a participant in the conversation."""
    name: str
    role: Optional[str] = None
    company: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)

class CompanyInfo(BaseModel):
    """Information about the company discussed."""
    name: str
    industry: Optional[IndustryType] = None
    stage: Optional[CompanyStage] = None
    revenue: Optional[float] = None
    growth_rate: Optional[float] = None
    location: Optional[str] = None

class NextStep(BaseModel):
    """Represents a next step or action item."""
    description: str
    owner: Optional[str] = None
    deadline: Optional[datetime] = None
    status: str = "pending"

class ProcessingState(BaseModel):
    """Main state object for tracking transcription processing."""
    # Input
    transcript: str
    transcript_id: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # Analysis
    summary: str = ""
    participants: List[Participant] = Field(default_factory=list)
    company_info: Optional[CompanyInfo] = None
    next_steps: List[NextStep] = Field(default_factory=list)
    key_points: List[str] = Field(default_factory=list)
    
    # Decision
    decision: Optional[DecisionType] = None
    decision_confidence: float = 0.0
    decision_reasoning: str = ""
    
    # Metadata
    processed_at: datetime = Field(default_factory=datetime.now)
    processing_duration: float = 0.0
    metadata: Dict = Field(default_factory=dict)