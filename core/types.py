from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime

class DecisionType(str, Enum):
    """Types of decisions that can be made about a transcription."""
    FUND_X = "fund_x"  # For non-urgent fund decisions
    FOLLOW_UP = "follow_up"  # For urgent follow-ups
    FUTURE_FUND = "future_fund"  # For future fund opportunities
    NO_ACTION = "no_action"  # For opportunities we're passing on

class IndustryType(str, Enum):
    """Industry categories for classification."""
    AI = "ai"
    SAAS = "saas"
    FINTECH = "fintech"
    HEALTHCARE = "healthcare"
    BIOTECH = "biotech"
    OTHER = "other"

class CompanyStage(str, Enum):
    """Company funding/growth stages."""
    SEED = "seed"
    SERIES_A = "series_a"
    SERIES_B = "series_b"
    SERIES_C = "series_c"
    GROWTH = "growth"

class ProcessingError(Exception):
    """Base exception for processing errors."""
    pass

class ValidationError(ProcessingError):
    """Raised when input validation fails."""
    pass

class IntegrationError(ProcessingError):
    """Raised when an external integration fails."""
    pass

class DDCategory(str, Enum):
    """Categories of due diligence checks."""
    TECHNICAL = "technical"
    FINANCIAL = "financial"
    MARKET = "market"
    TEAM = "team"
    LEGAL = "legal"
    PRODUCT = "product"
    CUSTOMER = "customer"
    OPERATIONAL = "operational"

class DDStatus(str, Enum):
    """Status of due diligence items."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FLAGGED = "flagged"

class DDPriority(str, Enum):
    """Priority levels for due diligence items."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
