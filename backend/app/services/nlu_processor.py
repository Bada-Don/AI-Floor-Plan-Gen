# app/services/nlu_processor.py
import httpx
import json
import re
from app.config import Config

def extract_json_from_response(text: str):
    """Extract JSON from AI response that might contain markdown or extra text"""
    try:
        # Try direct JSON parsing first
        return json.loads(text)
    except json.JSONDecodeError:
        # Look for JSON in markdown code blocks
        json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        match = re.search(json_pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Look for standalone JSON objects
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        raise json.JSONDecodeError("No valid JSON found in response")

def validate_and_fix_constraints(constraints):
    """Validate and fix common AI mistakes in constraints"""
    if not isinstance(constraints, dict):
        return {"error": "Invalid constraint format"}
    
    # Ensure plot exists with reasonable dimensions
    if "plot" not in constraints or not isinstance(constraints["plot"], dict):
        constraints["plot"] = {"width": 40, "height": 30}  # Default house size
    
    plot = constraints["plot"]
    try:
        width = float(plot.get("width", 40))
        height = float(plot.get("height", 30))
        
        # Sanity check dimensions
        if width < 20 or width > 200:
            print(f"Warning: Unusual plot width {width}, clamping to reasonable range")
            width = max(20, min(200, width))
        if height < 20 or height > 200:
            print(f"Warning: Unusual plot height {height}, clamping to reasonable range") 
            height = max(20, min(200, height))
            
        plot["width"] = width
        plot["height"] = height
    except (ValueError, TypeError):
        plot["width"] = 40
        plot["height"] = 30
    
    # Ensure rooms list exists
    if "rooms" not in constraints:
        constraints["rooms"] = []
    
    # Validate and fix room data
    valid_rooms = []
    has_entrance = False
    
    for room in constraints.get("rooms", []):
        if not isinstance(room, dict):
            continue
            
        room_type = str(room.get("type", "")).lower().strip()
        if not room_type:
            continue
            
        # Normalize room types
        if "entrance" in room_type or "entry" in room_type:
            room_type = "entrance"
            has_entrance = True
        elif "living" in room_type or "family" in room_type:
            room_type = "living room"
        elif "dining" in room_type:
            room_type = "dining room"
        elif "master" in room_type or "primary" in room_type:
            room_type = "master bedroom"
        elif "bed" in room_type:
            room_type = "bedroom"
        elif "bath" in room_type:
            room_type = "bathroom"
        elif "kitchen" in room_type:
            room_type = "kitchen"
        
        # Validate count and area
        try:
            count = max(1, int(room.get("count", 1)))
        except (ValueError, TypeError):
            count = 1
            
        try:
            area = float(room.get("area", 0))
            if area <= 0:  # Provide reasonable defaults
                area = {
                    "entrance": 30, "living room": 200, "dining room": 150,
                    "master bedroom": 180, "bedroom": 120, "bathroom": 50,
                    "kitchen": 150
                }.get(room_type, 100)
        except (ValueError, TypeError):
            area = 100
        
        valid_rooms.append({
            "type": room_type,
            "count": count,
            "area": area
        })
    
    # Add entrance if missing
    if not has_entrance:
        valid_rooms.insert(0, {"type": "entrance", "count": 1, "area": 30})
    
    constraints["rooms"] = valid_rooms
    
    # Ensure features list exists and is in the correct format
    if "features" not in constraints:
        constraints["features"] = []
    else:
        validated_features = []
        for feature in constraints.get("features", []):
            if isinstance(feature, str):
                validated_features.append({"type": feature.lower()})
            elif isinstance(feature, dict) and "type" in feature:
                validated_features.append(feature)
        constraints["features"] = validated_features
    
    return constraints

def get_fallback_constraints(text: str):
    """Generate reasonable fallback constraints based on text analysis"""
    text_lower = text.lower()
    
    # Extract numbers that might be dimensions
    numbers = [float(x) for x in re.findall(r'\b\d+(?:\.\d+)?\b', text)]
    
    # Guess plot size
    plot_width = 40  # Default
    plot_height = 30
    
    if len(numbers) >= 2:
        # Assume first two numbers might be plot dimensions
        plot_width = max(20, min(200, numbers[0]))
        plot_height = max(20, min(200, numbers[1]))
    
    # Count room mentions
    room_counts = {}
    room_keywords = {
        "bedroom": ["bedroom", "bed room", "br"],
        "bathroom": ["bathroom", "bath room", "bath", "toilet"],
        "living room": ["living", "family", "great room"],
        "kitchen": ["kitchen", "cook"],
        "dining room": ["dining", "eat"]
    }
    
    for room_type, keywords in room_keywords.items():
        count = sum(text_lower.count(keyword) for keyword in keywords)
        if count > 0:
            room_counts[room_type] = min(count, 5)  # Cap at 5 rooms
    
    # Build rooms list
    rooms = [{"type": "entrance", "count": 1, "area": 30}]  # Always need entrance
    
    for room_type, count in room_counts.items():
        area = {"bedroom": 120, "bathroom": 50, "living room": 200, 
                "kitchen": 150, "dining room": 120}.get(room_type, 100)
        rooms.append({"type": room_type, "count": count, "area": area})
    
    # Add defaults if no rooms found
    if len(rooms) == 1:  # Only entrance
        rooms.extend([
            {"type": "living room", "count": 1, "area": 200},
            {"type": "kitchen", "count": 1, "area": 150},
            {"type": "bedroom", "count": 2, "area": 120},
            {"type": "bathroom", "count": 1, "area": 50}
        ])
    
    return {
        "plot": {"width": plot_width, "height": plot_height},
        "rooms": rooms,
        "features": []
    }

async def parse_freeform_to_constraints(text: str):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={Config.GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}

    prompt = f"""
    You are an architectural AI that converts floor plan descriptions into JSON for a sophisticated layout generator.

    ARCHITECTURAL REASONING FRAMEWORK:
    
    **Building Analysis:**
    - Identify building type and primary function
    - Determine circulation patterns and flow requirements
    - Consider zone relationships (public/service/private)
    - Account for structural and code requirements
    
    **Space Programming Logic:**
    
    *Essential Spaces (always include):*
    - Entrance: 20-60 sq ft (circulation hub, exterior access)
    - Primary circulation: hallways connecting zones
    
    *Residential Requirements:*
    - Kitchen: 80-200 sq ft (service zone, adjacent to living)
    - Living/dining: 150-400 sq ft (public zone, central location)
    - Master bedroom: 150-300 sq ft (private zone, exterior wall)
    - Bedrooms: 80-150 sq ft each (private zone, exterior walls)
    - Bathrooms: 25-100 sq ft (service access to bedrooms)
    
    *Commercial Requirements:*
    - Reception/waiting: 100-200 sq ft (public zone)
    - Work areas: 80-150 sq ft per person
    - Storage: 10-15% of total program
    - Restrooms: code-required, service zone
    
    **Area Calculation Rules:**
    - Extract explicit areas when given
    - For room counts >1, distribute total area logically
    - Add 15-25% circulation factor to room areas
    - Ensure minimum dimensions: bedrooms 8'×10', bathrooms 5'×8', kitchens 8'×10'
    
    **Plot Sizing Strategy:**
    - Calculate total interior need (rooms + circulation)
    - Add structural factor: residential +20-30%, commercial +15-25%
    - Consider realistic proportions: residential 1:1 to 2:1, office varies
    - Minimum plot: 20' × 20' for any functional layout
    
    **Feature Identification:**
    - Architectural: fireplaces, built-ins, stairs, columns
    - Mechanical: HVAC, plumbing, electrical
    - Access: windows, doors, skylights
    - Outdoor: patios, decks, landscaping
    - Storage: closets, pantries, utility rooms
    
    **Smart Defaults for Missing Information:**
    - No bathroom mentioned → add 1 bathroom (50 sq ft)
    - No kitchen in residential → add kitchen (120 sq ft)
    - Multiple bedrooms but no master → designate largest as master
    - Commercial space → add restrooms and storage
    - No entrance specified → add entrance (30 sq ft)
    
    REQUIRED JSON SCHEMA (EXACT FORMAT):
    {{
      "plot": {{ "width": <number>, "height": <number> }},
      "rooms": [{{ "type": "<room_name>", "count": <number>, "area": <number> }}],
      "features": []
    }}
    
    **Room Type Standardization:**
    - Use: "living", "kitchen", "bedroom", "master", "bathroom", "entrance"
    - For dining areas: combine as "living" (the engine handles "Living/dining")
    - For home offices: use "bedroom" with appropriate area
    - For utility rooms: include in "features" array
    
    **Quality Validation:**
    ✓ All numbers are numeric (no units like 'ft', 'sqft')
    ✓ Always include "entrance" in rooms array
    ✓ Room areas realistic for function (kitchen ≥80, bedroom ≥80, bathroom ≥25)
    ✓ Total room area is 60-80% of plot area (allows for walls/circulation)
    ✓ Plot dimensions create buildable footprint
    ✓ Features include architectural/mechanical elements as strings
    
    Description: "{text}"
    
    Analyze the architectural program systematically, then provide ONLY the JSON response:"""


    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.1  # Lower temperature for more consistent JSON
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=30.0)
        
        resp.raise_for_status()
        data = resp.json()
        
        model_text = data["candidates"][0]["content"]["parts"][0]["text"]
        print(f"Raw AI response: {model_text}")
        
        # Try robust JSON extraction
        try:
            constraints = extract_json_from_response(model_text)
        except json.JSONDecodeError:
            print("JSON extraction failed, using fallback constraints")
            return get_fallback_constraints(text)
        
        # Validate and fix the constraints
        validated_constraints = validate_and_fix_constraints(constraints)
        if "error" in validated_constraints:
            return get_fallback_constraints(text)
            
        return validated_constraints
        
    except httpx.RequestError as e:
        print(f"Network request failed: {e}")
        return get_fallback_constraints(text)
    except (KeyError, IndexError) as e:
        print(f"Unexpected API response format: {e}")
        return get_fallback_constraints(text)
