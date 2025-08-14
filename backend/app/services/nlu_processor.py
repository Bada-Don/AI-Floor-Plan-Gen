import requests
import json
from app.config import Config

def normalize_constraints(c):
    try:
        if "plot" in c and isinstance(c["plot"], dict):
            c["plot"]["width"] = float(c["plot"].get("width", 0))
            c["plot"]["height"] = float(c["plot"].get("height", 0))
        
        if "rooms" in c and isinstance(c["rooms"], list):
            for r in c["rooms"]:
                if isinstance(r, dict):
                    r["count"] = int(r.get("count", 0))
    except (ValueError, TypeError) as e:
        print(f"Error normalizing constraints: {e}")
        # Optionally, you could raise an exception or return an error structure
        # For now, it will leave the values as they are if conversion fails
        pass
    return c

def parse_freeform_to_constraints(text: str):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={Config.GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}

    prompt = f"""
    Convert the following floor plan description into strict JSON with numeric values for all dimensions and counts.
    The JSON must follow exactly this schema:
    {{
      "plot": {{ "width": <number>, "height": <number> }},
      "rooms": [{{ "type": "<string>", "count": <number> }}, ...],
      "features": [{{ "type": "<string>", "zone": "<string>" }}, ...]
    }}
    Do not include units (like 'ft') in numbers. Output only pure JSON.
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

    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()

    data = resp.json()
    try:
        model_text = data["candidates"][0]["content"]["parts"][0]["text"]
        constraints = json.loads(model_text)
        return normalize_constraints(constraints)
    except Exception as e:
        print(f"Error parsing or normalizing Gemini response: {e}")
        raw_response = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "N/A")
        return {
            "error": "Failed to process Gemini response",
            "details": str(e),
            "raw_response": raw_response
        }