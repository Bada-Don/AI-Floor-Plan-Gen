# Pydantic request models
from pydantic import BaseModel
from typing import Optional, Dict, Any

class FreeformInput(BaseModel):
    text: str

class StructuredInput(BaseModel):
    constraints: Dict[str, Any]

class ChangeEvent(BaseModel):
    action: str
    target: str
    changes: Dict[str, Any]

class GenerateLayoutRequest(BaseModel):
    mode: str  # "freeform" or "structured"
    freeform: Optional[FreeformInput]
    structured: Optional[StructuredInput]
    sessionId: Optional[str]
    changeEvent: Optional[ChangeEvent]
