from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from .types import (
    DecisionType, 
    IndustryType, 
    CompanyStage,
    DDCategory,
    DDStatus,
    DDPriority
)

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

class DDRequirement(BaseModel):
    """Represents a specific due diligence requirement."""
    category: DDCategory
    description: str
    priority: DDPriority
    status: DDStatus = DDStatus.NOT_STARTED
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    evidence_required: List[str] = Field(default_factory=list)
    evidence_provided: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.now)

class DDPlan(BaseModel):
    """Overall due diligence plan."""
    requirements: List[DDRequirement] = Field(default_factory=list)
    status: DDStatus = DDStatus.NOT_STARTED
    start_date: Optional[datetime] = None
    target_completion_date: Optional[datetime] = None
    overall_progress: float = 0.0
    key_findings: List[str] = Field(default_factory=list)
    risk_assessment: Dict[str, str] = Field(default_factory=dict)

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

    # DD-related fields
    dd_plan: Optional[DDPlan] = None
    follow_up_questions: List[str] = Field(default_factory=list)
    risk_factors: List[str] = Field(default_factory=list)
    required_materials: List[str] = Field(default_factory=list)
