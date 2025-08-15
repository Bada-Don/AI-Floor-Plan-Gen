# floorplan/generator.py
import math, random, io, base64
import matplotlib
matplotlib.use("Agg") # Use non-GUI backend for server environment
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from collections import deque, namedtuple
from typing import Dict, Any, List, Tuple

# === Architectural Rules & Constants ===
MUST_BE_ADJACENT = {"kitchen": "living"}
MUST_NOT_BE_ADJACENT = {"master": ["living", "kitchen"], "bedroom": ["living", "kitchen"]}
# NEW: Add Proximity to scoring weights
WEIGHT_ADJACENCY = 20.0
WEIGHT_PROXIMITY = 15.0 # NEW: Encourages tight packing
WEIGHT_ENVIRONMENTAL = 10.0
WEIGHT_STRUCTURAL = 8.0
WEIGHT_PROPORTIONS = 5.0
GRID_SPACING_FT = 4
DEFAULT_MIN_SIZES = { "bedroom": (8, 9), "master": (12, 12), "bathroom": (5, 7), "kitchen": (8, 10), "living": (10, 12), "entrance": (5, 5), "corridor": (4, 20)}
MAX_AREA_COVERAGE_RATIO = 0.80

# === Core Definitions (largely unchanged) ===
Cell = namedtuple("Cell", ["x","y"])
class Grid:
    def __init__(self, width_ft, height_ft, cell_ft=1): self.cell, self.cols, self.rows = cell_ft, int(width_ft // cell_ft), int(height_ft // cell_ft)
class RoomSpec:
    def __init__(self, name, room_type, area_ft2=None, prefs=None, priority=5): self.name, self.type, self.area, self.prefs, self.priority = name, room_type, area_ft2, prefs or {}, priority
class PlacedRoom:
    def __init__(self, spec:RoomSpec, x, y, w, h, zone="private"): self.spec, self.name, self.type, self.x, self.y, self.w, self.h, self.zone = spec, spec.name, spec.type, x, y, w, h, zone
    def cells(self):
        for i in range(self.x, self.x+self.w):
            for j in range(self.y, self.y+self.h): yield (i,j)
    @property
    def area_sq_ft(self): return self.spec.prefs.get('placed_area', self.w * self.h)
    def bbox(self): return (self.x, self.y, self.w, self.h)
    def center(self): return (self.x + self.w / 2, self.y + self.h / 2)

def ft_to_cells(dim_ft, cell_ft=1): return max(1, int(round(dim_ft / cell_ft)))
def area_to_wh_cells(area_ft2, cell_ft=1, preferred_aspect=1.2):
    cells = max(1, int(round(area_ft2/(cell_ft*cell_ft)))); h = max(1, int(round(math.sqrt(cells/preferred_aspect)))); w = max(1, int(round(cells/h))); return w, h

# === Floor Plan Generator v3.3 (Cohesive Zones & Intelligent Scaling) ===
class FloorPlanGenerator:
    def __init__(self, plot_w_ft, plot_h_ft, cell_ft=1, verbose=False):
        self.grid = Grid(plot_w_ft, plot_h_ft, cell_ft)
        self.cell_ft = cell_ft; self.placed = []; self.verbose = verbose
        self.occupied = [[None]*self.grid.rows for _ in range(self.grid.cols)]
        self.grid_spacing_cells = ft_to_cells(GRID_SPACING_FT, self.cell_ft)

    # --- Core Utilities ---
    def get_rooms_by_type(self, rtype): return [r for r in self.placed if r.type == rtype]
    def get_room_zone(self, rtype):
        if rtype in ("living", "entrance", "corridor"): return "public"
        if rtype == "kitchen": return "service"
        return "private"
    def check_space_free(self, x,y,w,h):
        if x<0 or y<0 or x+w>self.grid.cols or y+h>self.grid.rows: return False
        for i in range(x,x+w):
            for j in range(y,y+h):
                if self.occupied[i][j] is not None: return False
        return True
    def place_room(self, spec, x,y,w,h, zone, placed_area):
        spec.prefs['placed_area'] = int(placed_area)
        pr = PlacedRoom(spec, x,y,w,h, zone=zone)
        self.placed.append(pr)
        for i in range(x, x + w):
            for j in range(y, y + h):
                self.occupied[i][j] = pr.name
        return pr
    def calculate_shared_wall_length(self, room1, room2):
        if not room1 or not room2: return 0
        r1_cells = set(room1.cells()); shared_len = 0
        for x, y in room2.cells():
            for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                if (x+dx, y+dy) in r1_cells: shared_len += 1
        return shared_len

    # --- NEW: Multi-Factor Scoring Engine with Proximity ---
    def _score_proximity(self, x, y, w, h, anchors):
        if not anchors: return 0
        avg_ax = sum(a.center()[0] for a in anchors) / len(anchors)
        avg_ay = sum(a.center()[1] for a in anchors) / len(anchors)
        dist = math.sqrt((x + w/2 - avg_ax)**2 + (y + h/2 - avg_ay)**2)
        # Penalize distance heavily to encourage packing
        return -dist * 2.0

    def score_candidate(self, spec, x, y, w, h, meta, anchors):
        # (Previous scoring logic is sound, we just add proximity to it)
        temp_room = PlacedRoom(spec, x, y, w, h, self.get_room_zone(spec.type))
        adj_score = 0
        if spec.type in MUST_NOT_BE_ADJACENT:
            for other_type in MUST_NOT_BE_ADJACENT[spec.type]:
                for other_room in self.get_rooms_by_type(other_type):
                    if self.calculate_shared_wall_length(temp_room, other_room) > 0: return -1e9
        if spec.type in MUST_BE_ADJACENT:
            # Check against all living rooms for kitchen placement
            living_rooms = self.get_rooms_by_type('living')
            if living_rooms and not any(self.calculate_shared_wall_length(temp_room, lr) > ft_to_cells(4) for lr in living_rooms):
                return -1e9 # Must be adjacent to at least one living room
            adj_score += 100

        prox_score = self._score_proximity(x, y, w, h, anchors)
        env_score = 0; front = meta.get("front_direction", "south")
        if spec.type in ("living", "master"):
            if front == "south" and y + h >= self.grid.rows: env_score += w * 1.5
            elif front == "north" and y == 0: env_score += w * 1.5
        grid = self.grid_spacing_cells
        struct_score = 0
        if grid > 0: struct_score = -(min(x % grid, grid - x % grid) + min(y % grid, grid - y % grid))
        aspect = max(w,h) / max(1, min(w,h)); prop_score = -10 * (aspect - 2.0) if aspect > 2.0 else 0

        return (adj_score * WEIGHT_ADJACENCY + prox_score * WEIGHT_PROXIMITY + env_score * WEIGHT_ENVIRONMENTAL + struct_score * WEIGHT_STRUCTURAL + prop_score * WEIGHT_PROPORTIONS)

    # --- Strategic Placement Engine ---
    def _place_central_corridor(self, corridor_spec):
        if not corridor_spec: return None
        h = ft_to_cells(DEFAULT_MIN_SIZES['corridor'][0], self.cell_ft); w = self.grid.cols
        x=0; y = int(self.grid.rows * 0.4) # Place corridor slightly higher up
        if self.check_space_free(x, y, w, h):
            return self.place_room(corridor_spec, x, y, w, h, "public", w*h*self.cell_ft**2)
        return None

    def _find_placement_candidates(self, w, h, anchors):
        all_candidates = set()
        for anchor_room in anchors:
            if not anchor_room: continue
            ax, ay, aw, ah = anchor_room.bbox()
            for i in range(-w + 1, aw):
                all_candidates.add((ax + i, ay - h)); all_candidates.add((ax + i, ay + ah))
            for j in range(-h + 1, ah):
                all_candidates.add((ax - w, ay + j)); all_candidates.add((ax + aw, ay + j))
        valid_candidates = [(x, y) for x, y in all_candidates if self.check_space_free(x, y, w, h)]
        if not valid_candidates:
            for x in range(0, self.grid.cols - w + 1, self.grid_spacing_cells or 4):
                 for y in range(0, self.grid.rows - h + 1, self.grid_spacing_cells or 4):
                     if self.check_space_free(x, y, w, h): valid_candidates.append((x,y))
        return valid_candidates

    def _attempt_placement(self, spec, w, h, meta, anchors):
        for rot_w, rot_h in [(w,h), (h,w)]:
            candidates = self._find_placement_candidates(rot_w, rot_h, anchors)
            if not candidates: continue
            scored = sorted([(x, y, self.score_candidate(spec, x, y, rot_w, rot_h, meta, anchors)) for x, y in candidates], key=lambda i: i[2], reverse=True)
            if scored and scored[0][2] > -1e8:
                best = scored[0]
                self.place_room(spec, best[0], best[1], rot_w, rot_h, zone=self.get_room_zone(spec.type), placed_area=rot_w*rot_h*self.cell_ft**2)
                return True
        return False

    def _find_and_place_room(self, spec, meta, anchors):
        # Simplified: The intelligent scaling in the adapter removes the need for complex fallbacks here
        w, h = area_to_wh_cells(spec.area, self.cell_ft)
        if not self._attempt_placement(spec, w, h, meta, anchors):
             print(f"Error: Failed to place room: {spec.name}")
             return False
        return True

    # --- Main Generation Method (NEW DYNAMIC ANCHORING) ---
    def generate(self, specs, meta):
        # 1. Place Entrance & Corridor
        entrance_spec = next((s for s in specs if s.type=="entrance"), None)
        if entrance_spec:
            ew, eh = area_to_wh_cells(entrance_spec.area, self.cell_ft)
            ex = self.grid.cols // 2 - ew // 2; ey = self.grid.rows - eh
            self.place_room(entrance_spec, ex, ey, ew, eh, "public", ew*eh*self.cell_ft**2)
        corridor_spec = next((s for s in specs if s.type=="corridor"), None)
        corridor = self._place_central_corridor(corridor_spec)
        
        # 2. Sequentially place rooms with DYNAMIC anchors
        public_specs = [s for s in specs if s.type in ('living', 'kitchen')]
        private_specs = [s for s in specs if s.type in ('master', 'bedroom')]
        bathroom_specs = [s for s in specs if 'bath' in s.type]

        # Public Zone - dynamically grows
        public_anchors = [self.placed[0] if self.placed else None, corridor]
        for spec in sorted(public_specs, key=lambda s: 1 if s.type == 'kitchen' else 2): # Place kitchen last
            self._find_and_place_room(spec, meta, [a for a in public_anchors if a])
            # Add the newly placed room to the anchor list for the next one
            newly_placed = next((r for r in self.placed if r.name == spec.name), None)
            if newly_placed: public_anchors.append(newly_placed)

        # Private Zone - dynamically grows
        private_anchors = [corridor]
        for spec in sorted(private_specs, key=lambda s: 1 if s.type == 'master' else 2):
            self._find_and_place_room(spec, meta, [a for a in private_anchors if a])
            newly_placed = next((r for r in self.placed if r.name == spec.name), None)
            if newly_placed: private_anchors.append(newly_placed)
        
        # Place bathrooms, anchoring to the now-complete private zone
        for spec in bathroom_specs:
            self._find_and_place_room(spec, meta, [a for a in private_anchors if a])

        message = "Layout generated successfully."
        return True, message, meta

    def render_base_64(self, title="Floor Plan"):
        # (Renamed for consistency, but logic is the same)
        cols, rows = self.grid.cols, self.grid.rows; fig, ax = plt.subplots(figsize=(max(8, cols/5), max(8, rows/5)))
        colors = {"public":"#98FB98","private":"#87CEEB","service":"#FFA07A", "storage":"#DDDDDD"}
        for r in self.placed:
            rect = patches.Rectangle((r.x,r.y),r.w,r.h,facecolor=colors.get(r.zone,"#DDD"),edgecolor="black",linewidth=1.1, alpha=0.8)
            ax.add_patch(rect); ax.text(r.x+r.w/2,r.y+r.h/2,f"{r.name}\n({r.area_sq_ft} sqft)",ha="center",va="center",fontsize=7,wrap=True)
        ent = next((r for r in self.placed if r.type=='entrance'), None)
        if ent: ax.plot(ent.center()[0], ent.center()[1], 'o', color="red", markersize=8)
        ax.set_xlim(-1,cols+1); ax.set_ylim(-1,rows+1); ax.set_aspect("equal"); ax.axis("off"); ax.set_title(title,fontsize=14,fontweight="bold"); plt.gca().invert_yaxis()
        buf = io.BytesIO(); plt.savefig(buf, format='png', bbox_inches='tight'); plt.close(fig); buf.seek(0)
        return base64.b64encode(buf.getvalue()).decode('utf-8')

# --- Adapter Function (NEW INTELLIGENT SCALING LOGIC) ---
def generate_layout_from_constraints(constraints: Dict[str, Any]) -> Tuple[Dict[str, Any], Any]:
    lot = constraints.get("plot",{}); w,h = lot.get("width",0), lot.get("height",0)
    if not w or not h: return {"error": "Invalid plot dimensions."}, None
    
    specs = []
    room_constraints = constraints.get("rooms", []) or []
    
    # --- NEW: Intelligent Scaling with Minimum Size Guarantee ---
    plot_area = w * h
    available_area = plot_area * MAX_AREA_COVERAGE_RATIO
    
    # Step 1: Create initial specs and calculate total requested area
    initial_specs = []
    total_requested_area = 0
    for item in room_constraints:
        # (Room type normalization logic from v3.2)
        rtype_base = item.get("type", "other").lower()
        if "liv" in rtype_base or "din" in rtype_base: rtype = "living"
        elif "master" in rtype_base and "bath" in rtype_base: rtype = "master_bathroom"
        elif "master" in rtype_base: rtype = "master"
        elif "bed" in rtype_base: rtype = "bedroom"
        elif "bath" in rtype_base: rtype = "bathroom"
        elif "kitch" in rtype_base: rtype = "kitchen"
        elif "entran" in rtype_base: rtype = "entrance"
        else: continue
        
        count = int(item.get("count",1))
        total_area_for_type = item.get("area", 100 * count)
        total_requested_area += total_area_for_type
        initial_specs.append({'type': rtype, 'count': count, 'total_area': total_area_for_type})

    # Step 2: If oversized, perform intelligent scaling
    if total_requested_area > available_area:
        print(f"Warning: Requested area ({total_requested_area:.0f} sqft) exceeds buildable area ({available_area:.0f} sqft). Scaling rooms...")
        
        # First, guarantee minimum size for all rooms
        guaranteed_area = 0
        for spec_info in initial_specs:
            min_dims = DEFAULT_MIN_SIZES.get(spec_info['type'], (5,5))
            min_area = min_dims[0] * min_dims[1]
            spec_info['min_total_area'] = min_area * spec_info['count']
            guaranteed_area += spec_info['min_total_area']
        
        # Check if even the minimums are too large
        if guaranteed_area > available_area:
            return {"error": f"Plot is too small. Minimum required area is {guaranteed_area:.0f} sqft, but only {available_area:.0f} is available."}, None
        
        # Distribute the *remaining* space proportionally
        remaining_area_to_distribute = available_area - guaranteed_area
        overage_area = total_requested_area - guaranteed_area
        
        for spec_info in initial_specs:
            # The proportion of the "extra" (above minimum) space this room type gets
            proportion_of_overage = (spec_info['total_area'] - spec_info['min_total_area']) / overage_area if overage_area > 0 else 0
            # Final area is its guaranteed minimum + its share of the remainder
            final_total_area = spec_info['min_total_area'] + (remaining_area_to_distribute * proportion_of_overage)
            spec_info['final_area_per_room'] = final_total_area / spec_info['count']
    else:
        # If not oversized, just calculate area per room
        for spec_info in initial_specs:
            spec_info['final_area_per_room'] = spec_info['total_area'] / spec_info['count']
    
    # Step 3: Create the final RoomSpec objects for the generator
    room_counters = {}
    for spec_info in initial_specs:
        rtype = spec_info['type']
        for _ in range(spec_info['count']):
            room_counters[rtype] = room_counters.get(rtype, 0) + 1
            name = f"{rtype.capitalize()} {room_counters[rtype]}"
            # (Naming improvements from v3.2)
            if rtype == "master": name = "Master Bedroom"
            if rtype == "entrance" and spec_info['count'] == 1: name = "Entrance"
            if rtype == "kitchen" and spec_info['count'] == 1: name = "Kitchen"
            specs.append(RoomSpec(name, rtype, spec_info['final_area_per_room']))

    # Add essentials and run generator
    if not any(s.type == 'entrance' for s in specs): specs.insert(0, RoomSpec("Entrance","entrance",40,priority=0))
    if not any(s.type == 'corridor' for s in specs): specs.append(RoomSpec("Corridor", "corridor", area_ft2=w*4))

    gen = FloorPlanGenerator(w,h)
    meta = {"entrance_side": "south", "front_direction": "south", "features": [item.get("type") for item in constraints.get("features", [])]}
    ok,msg,meta_out = gen.generate(specs, meta)
    
    return {
        "lot":lot,
        "features":gen.placed,
        "image_base_64":gen.render_base_64(),
        "status":"ok" if ok else "failed",
        "message":msg
    }, gen.placed