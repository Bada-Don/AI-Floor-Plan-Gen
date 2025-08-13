# Gemini prompt → constraints JSON
import requests
from app.config import Config

def parse_freeform_to_constraints(freeform_text: str) -> dict:
    prompt = f"""
    You are an AI that converts floor plan descriptions into structured constraints.
    Input: "{freeform_text}"
    Output as JSON with keys: rooms, features, placement.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {Config.GEMINI_API_KEY}"
    }
    resp = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
        headers=headers,
        json={"contents": [{"parts": [{"text": prompt}]}]}
    )
    resp.raise_for_status()
    data = resp.json()
    raw_text = data['candidates'][0]['content']['parts'][0]['text']
    import json
    return json.loads(raw_text)
