# Matplotlib → SVG/PNG output
from typing import Dict, Any, List

# Minimal color palette for conceptual plans
DEFAULT_COLORS = {
    "lot": "#f8f9fa",
    "park": "#b9e6a4",
    "pool": "#9bd3f0",
    "entrance": "#f5c16c",
    "living": "#f9dcc4",
    "kitchen": "#f4bfbf",
    "bedroom": "#d0bdf4",
    "bathroom": "#b8c0ff",
    "hallway": "#d3f8e2",
    "other": "#e5e5e5"
}

def _color_for(type_name: str) -> str:
    t = type_name.lower()
    for key in DEFAULT_COLORS:
        if key != "lot" and key in t:
            return DEFAULT_COLORS[key]
    return DEFAULT_COLORS["other"]

def render_svg(layout: Dict[str, Any], padding: int = 20) -> str:
    lot = layout["lot"]
    W, H = lot["width"], lot["height"]
    feats: List[Dict[str, Any]] = layout.get("features", [])

    # --- Scaling Logic ---
    TARGET_SVG_WIDTH = 600
    scale = TARGET_SVG_WIDTH / W
    width_px = int(TARGET_SVG_WIDTH + padding * 2)
    height_px = int(H * scale + padding * 2)

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px}" height="{height_px}" viewBox="0 0 {width_px} {height_px}">')
    
    # --- Styles ---
    svg.append('''<style>
        .label { font-family: Inter, system-ui, sans-serif; font-size: 14px; fill: #111; text-anchor: middle; dominant-baseline: middle; }
        .lot-label { font-size: 16px; font-weight: 500; }
    </style>''')

    # --- Lot ---
    svg.append(f'<rect x="0" y="0" width="{width_px}" height="{height_px}" fill="#ffffff" />')
    svg.append(f'<rect x="{padding}" y="{padding}" width="{W * scale}" height="{H * scale}" fill="{DEFAULT_COLORS["lot"]}" stroke="#111" stroke-width="2"/>')
    svg.append(f'<text x="{padding + W * scale / 2}" y="{height_px - padding / 2}" class="label lot-label">Lot: {W}ft x {H}ft</text>')

    # --- Features ---
    for f in feats:
        x = padding + f["x"] * scale
        y = padding + f["y"] * scale
        w = f["width"] * scale
        h = f["height"] * scale
        label = f.get("label", f["type"].title())
        color = f.get("color") or _color_for(f["type"])
        
        # Skip rendering if feature is too small to be visible
        if w < 1 or h < 1:
            continue

        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{color}" stroke="#333" stroke-width="1.5" rx="4" ry="4"/>')
        
        # --- Labeling ---
        # Add dimensions below the main label
        dim_text = f'{f["width"]:.1f} x {f["height"]:.1f} ft'
        font_size = max(10, min(w * 0.12, h * 0.12, 16)) # Dynamic font size
        
        svg.append(f'<text x="{x + w/2}" y="{y + h/2 - font_size/2}" class="label" style="font-size:{font_size}px;">{label}</text>')
        svg.append(f'<text x="{x + w/2}" y="{y + h/2 + font_size/2 + 4}" class="label" style="font-size:{font_size*0.8}px; opacity:0.8;">{dim_text}</text>')

    svg.append("</svg>")
    return "".join(svg)
