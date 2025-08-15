# app/services/nlu_processor.py

import httpx  # <--- Use httpx instead of requests
import json
from app.config import Config

# This helper function doesn't do I/O, so it stays as a regular function
def normalize_constraints(c):
    try:
        if "plot" in c and isinstance(c["plot"], dict):
            c["plot"]["width"] = float(c["plot"].get("width", 0))
            c["plot"]["height"] = float(c["plot"].get("height", 0))
        
        if "rooms" in c and isinstance(c["rooms"], list):
            for r in c["rooms"]:
                if isinstance(r, dict):
                    r["count"] = int(r.get("count", 1)) # Default count to 1
    except (ValueError, TypeError) as e:
        print(f"Error normalizing constraints: {e}")
        pass
    return c

# --- CORRECTED: The function is now async ---
async def parse_freeform_to_constraints(text: str):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={Config.GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}

    prompt = f"""
    Convert the following floor plan description into a strict JSON object.

    Rules:
    1. All dimensions must be numeric values (width, height, area). Do not include units like 'ft'.
    2. The "rooms" list is for core living spaces.
    3. **You MUST always include an "entrance" room in the "rooms" list.**
    4. Provide a reasonable estimated 'area' in square feet for each room if not specified.
    5. The "features" list is for secondary, non-room elements or specific placement instructions.
    6. The JSON must follow exactly this schema:
    {{
      "plot": {{ "width": <number>, "height": <number> }},
      "rooms": [{{ "type": "<string>", "count": <number>, "area": <number> }}],
      "features": [{{ "type": "<string>", "zone": "<string>" }}]
    }}

    Input: "{text}"
    """

    payload = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "response_mime_type": "application/json"
        }
    }

    # --- CORRECTED: Use httpx's async client to make a non-blocking network request ---
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=30.0)
        
        resp.raise_for_status()
        data = resp.json()
        print(f"Gemini API raw response: {json.dumps(data, indent=2)}")

        model_text = data["candidates"][0]["content"]["parts"][0]["text"]
        constraints = json.loads(model_text)
        return normalize_constraints(constraints)
        
    except httpx.RequestError as e:
        print(f"HTTPX request failed: {e}")
        return {
            "error": "Failed to contact AI service",
            "details": str(e)
        }
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"Error parsing or processing Gemini response: {e}")
        raw_response = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "N/A")
        return {
            "error": "Failed to parse AI response",
            "details": str(e),
            "raw_response": raw_response
        }