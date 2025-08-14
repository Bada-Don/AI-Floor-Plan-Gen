# 🏗 AI Floor Plan Generator

## 📌 Overview

The **AI Floor Plan Generator** is an interactive system that takes **natural language** or **structured input** describing a building plot and desired features, then **iteratively processes constraints** to generate a conceptual floor plan.

The goal is **not** to produce legal or CAD-grade blueprints, but to create **clear, visual conceptual layouts** that satisfy spatial requirements in a way that’s easy to refine.

This repository is organized into two main parts:

* **`/frontend`** — React-based UI with chat, undo/redo, and SVG preview
* **`/backend`** — FastAPI-powered API server that parses, validates, generates, and renders layouts

---

## 📂 Repository Structure

```
/frontend
  ├── public/              # Static assets
  ├── src/
  │   ├── components/      # React components (chat, preview, controls)
  │   ├── hooks/           # Custom React hooks (undo/redo, session state)
  │   ├── utils/           # Helper functions for SVG rendering, state mgmt
  │   ├── App.jsx          # Main application entry point
  │   ├── index.jsx        # React DOM bootstrap
  │   └── styles.css       # Global styles

/backend
  ├── app/
  │   ├── __init__.py
  │   ├── config.py        # App-wide settings & constants
  │   ├── main.py          # FastAPI app entry
  │   ├── routes/
  │   │   └── layout.py    # API endpoints for layout generation
  │   ├── models/
  │   │   ├── requests.py  # Pydantic request schemas
  │   │   └── responses.py # Pydantic response schemas
  │   ├── services/
  │   │   ├── nlu_processor.py # Converts natural language to constraints JSON
  │   │   ├── generator.py     # Core spatial layout algorithm
  │   │   ├── validator.py     # Checks feasibility & spatial conflicts
  │   │   └── renderer.py      # Converts layout JSON → SVG string
  │   └── tests/           # (Optional) Backend unit tests
  ├── requirements.txt     # Backend Python dependencies
  └── README.md            # (This file)

/docs
  └── architecture.md      # Detailed system flow and diagrams
```

---

## ⚙️ How It Works

### 1️⃣ **User Interaction**

* The user begins in the **chat interface** (`/frontend`).
* They describe their requirements either:

  * **Freeform** — e.g. *“I want a park (30x20) on the left, a pool (15x10) on the right, and an entrance in the middle, plus 2 bedrooms and a kitchen”*
  * **Structured Form** — via input fields for plot size, room list, special features, etc.
* The **Chatbot** (LLM, using Gemini API) helps clarify requirements before generation.

  * It asks follow-up questions.
  * It confirms ambiguous sizes or positions.

---

### 2️⃣ **Frontend → Backend**

* The frontend sends the request to:

  ```
  POST /generate-layout
  ```
* Request format follows the schema in `app/models/requests.py`:

  ```json
  {
    "mode": "freeform",
    "freeform": {
      "text": "park 30x20 on left, pool 15x10 on right, entrance middle, 2 bedrooms, 1 kitchen, 1 hall"
    }
  }
  ```
* Or structured:

  ```json
  {
    "mode": "structured",
    "structured": {
      "constraints": {
        "plot": { "width": 100, "height": 60 },
        "rooms": [{ "type": "bedroom", "count": 2 }, { "type": "kitchen", "count": 1 }],
        "features": [
          { "type": "park", "width": 30, "height": 60, "position": "left" },
          { "type": "pool", "width": 20, "height": 20, "position": "right" }
        ],
        "entrance": { "position": "south_center" }
      }
    }
  }
  ```

---

### 3️⃣ **Backend Processing Pipeline**

1. **NLU Processor (`nlu_processor.py`)**

   * In freeform mode: Parses text → structured constraints JSON using rule-based extraction or Gemini API.
   * In structured mode: Skips parsing and directly uses given JSON.

2. **Constraint Validation (`validator.py`)**

   * Checks plot dimensions.
   * Ensures all fixed feature sizes are valid.
   * Prevents impossible layouts (negative size, invalid positions).

3. **Layout Generation (`generator.py`)**

   * Places **fixed features** first (park left, pool right, entrance middle).
   * Calculates remaining available space.
   * Places **public areas** (living, kitchen, hallway).
   * Places **private areas** (bedrooms, bathrooms) while checking bathroom privacy.
   * Attempts simple auto-repair if conflicts arise.

4. **Final Validation (`validator.py`)**

   * Ensures no overlaps.
   * Checks all features are within plot bounds.
   * Checks bathroom–entrance privacy.

5. **Rendering (`renderer.py`)**

   * Converts layout JSON into a **SVG string**.
   * Uses color coding for room types.
   * Labels each feature.

---

### 4️⃣ **Backend → Frontend Response**

* **On success:**

  ```json
  {
    "lot": { "width": 100, "height": 60 },
    "features": [
      { "type": "park", "x": 0, "y": 0, "width": 30, "height": 60, "label": "Park", "locked": true },
      { "type": "pool", "x": 80, "y": 0, "width": 20, "height": 20, "label": "Pool", "locked": true }
    ],
    "svg": "<svg>...</svg>"
  }
  ```
* **On failure (conflicts):**

  ```json
  {
    "error": "Layout generation failed",
    "conflicts": ["Bedroom overlaps with Pool"],
    "suggestions": ["Reduce bedroom size", "Move pool further right"]
  }
  ```

---

## 🖥 Frontend Features

* **Chat-driven flow** to refine requirements.
* **Undo/Redo** for session state.
* **SVG preview panel** that updates live.
* **Structured form** for power users.
* **Conflict display** when backend returns validation issues.
* **Regenerate** button for quick iteration.

---

## 🛠 Backend Tech Stack

* **FastAPI** — lightweight, async Python API framework
* **Pydantic** — schema validation for requests/responses
* **Python-dotenv** — environment configuration
* **Custom Spatial Algorithms** — room placement & constraint satisfaction
* **SVG Renderer** — generates scalable vector diagrams for immediate preview

---

## 📦 Installation & Setup

### 1. Clone Repo

```bash
git clone https://github.com/Bada-Don/AI-Floor-Plan-Gen.git
cd AI-Floor-Plan-Gen
```

### 2. Setup Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 3. Run Backend

```bash
uvicorn app.main:app --reload
```

Backend will be at: `http://127.0.0.1:8000`

### 4. Setup Frontend

```bash
cd ../frontend
npm install
npm start
```

Frontend will be at: `http://localhost:3000`

---

## 🔄 Development Flow

1. **Change detection** — Frontend auto-refreshes on save (`npm start`).
2. **Backend reload** — FastAPI reloads on save (`--reload` flag).
3. **API Testing** — Use Postman or `curl` for direct backend checks.

---

## 🚀 MVP Scope

✅ Conversational input → structured constraints
✅ Core spatial layout algorithm
✅ SVG rendering
✅ Conflict detection & suggestions
✅ Quick regeneration loop

**Not included in MVP (future scope):**

* Real-world building codes/legal constraints
* Complex multi-floor designs
* State persistence/user accounts
* CAD export

---

## 🧭 Future Enhancements

* Persistent user sessions with editable saved layouts.
* Multiple floors & stair placement logic.
* AI-driven optimization for minimal wasted space.
* 3D preview using Three.js or Babylon.js.
* Advanced constraint solver for complex shapes.

---
