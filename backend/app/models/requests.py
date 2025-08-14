# app/models/requests.py
from pydantic import BaseModel
from typing import Optional, Dict, Any, Literal

class FreeformInput(BaseModel):
    text: str

class StructuredInput(BaseModel):
    constraints: Dict[str, Any]

class ChangeEvent(BaseModel):
    action: str
    target: str
    changes: Dict[str, Any]

class GenerateLayoutRequest(BaseModel):
    mode: Literal["freeform", "structured", "change"]
    freeform: Optional[FreeformInput] = None
    structured: Optional[StructuredInput] = None
    sessionId: Optional[str] = None
    changeEvent: Optional[ChangeEvent] = None
