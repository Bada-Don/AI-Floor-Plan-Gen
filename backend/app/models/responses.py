from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class Feature(BaseModel):
    type: str
    x: float
    y: float
    width: float
    height: float
    label: Optional[str] = None
    color: Optional[str] = None
    locked: Optional[bool] = False  # fixed pre-placement (e.g., park/pool/entrance)

class LayoutResponse(BaseModel):
    lot: Dict[str, float]
    features: List[Feature]
    image_base64: Optional[str] = None  # Add this field
    status: Optional[str] = None
    message: Optional[str] = None


class ConflictResponse(BaseModel):
    error: str
    conflicts: List[str]
    suggestions: List[str]
