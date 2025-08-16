# floorplan/generator.py
import math, random, io, base64, itertools, copy, heapq
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from collections import deque, namedtuple
from typing import Dict, Any, List, Tuple
from shapely.geometry import Polygon
from shapely.ops import unary_union
import networkx as nx # --- PHASE 2: Required for relationship graph ---


# === Architectural Rules & Constants (The Graph will now handle this) ===
WEIGHT_ADJACENCY = 50.0  # Increased weight as it's now more critical
WEIGHT_PROXIMITY = 10.0
WEIGHT_ENVIRONMENTAL = 10.0
WEIGHT_PROPORTIONS = 5.0
WEIGHT_RECTANGULARITY = 18.0
GRID_SPACING_FT = 4
DEFAULT_MIN_SIZES = { "bedroom": (8, 9), "master": (12, 12), "bathroom": (5, 7), "kitchen": (8, 10), "living": (10, 12), "entrance": (5, 5), "corridor": (4, 20)}
MAX_AREA_COVERAGE_RATIO = 0.80

# === Core Definitions (Unchanged) ===
Cell = namedtuple("Cell", ["x","y"])
class Grid:
    def __init__(self, width_ft, height_ft, cell_ft=1): self.cell, self.cols, self.rows = cell_ft, int(width_ft // cell_ft), int(height_ft // cell_ft)
class RoomSpec:
    def __init__(self, name, room_type, area_ft2=None, prefs=None, priority=5): self.name, self.type, self.area, self.prefs, self.priority = name, room_type, area_ft2, prefs or {}, priority
class PlacedRoom:
    def __init__(self, spec:RoomSpec, x, y, w, h, zone="private", fixed=False): # Added 'fixed' attribute
        self.spec, self.name, self.type, self.x, self.y, self.w, self.h, self.zone = spec, spec.name, spec.type, x, y, w, h, zone
        self.fixed = fixed # --- PHASE 2: To lock corridors in place
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

class FloorPlanGenerator:
    def __init__(self, plot_w_ft, plot_h_ft, cell_ft=1, verbose=False):
        self.grid = Grid(plot_w_ft, plot_h_ft, cell_ft)
        self.cell_ft = cell_ft; self.placed = []; self.verbose = verbose
        self.occupied = [[None]*self.grid.rows for _ in range(self.grid.cols)]
        self.grid_spacing_cells = ft_to_cells(GRID_SPACING_FT, self.cell_ft)
        self.openings = []

    # --- PHASE 2: A* Pathfinding for Circulation ---
    def _heuristic(self, a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _a_star_pathfinding(self, start, goal, obstacles):
        """Finds a path on the grid from start to goal, avoiding obstacles."""
        neighbors = [(0,1),(0,-1),(1,0),(-1,0)]
        close_set = set()
        came_from = {}
        gscore = {start:0}
        fscore = {start:self._heuristic(start, goal)}
        oheap = []
        heapq.heappush(oheap, (fscore[start], start))
        
        while oheap:
            current = heapq.heappop(oheap)[1]
            if current == goal:
                data = []
                while current in came_from:
                    data.append(current)
                    current = came_from[current]
                return data
            
            close_set.add(current)
            for i, j in neighbors:
                neighbor = current[0] + i, current[1] + j            
                if 0 <= neighbor[0] < self.grid.cols and 0 <= neighbor[1] < self.grid.rows:
                    if neighbor in obstacles or neighbor in close_set:
                        continue
                else:
                    continue
                    
                tentative_g_score = gscore[current] + 1
                
                if tentative_g_score < gscore.get(neighbor, 0) or neighbor not in [i[1]for i in oheap]:
                    came_from[neighbor] = current
                    gscore[neighbor] = tentative_g_score
                    fscore[neighbor] = tentative_g_score + self._heuristic(neighbor, goal)
                    heapq.heappush(oheap, (fscore[neighbor], neighbor))
        return [] # No path found

    # --- Core Utilities (Largely Unchanged) ---
    def get_rooms_by_type(self, rtype, layout: List[PlacedRoom]):
        return [r for r in layout if r.type == rtype]
    def get_room_zone(self, rtype):
        if rtype in ("living", "entrance", "corridor"): return "public"
        if rtype == "kitchen": return "service"
        return "private"
    def calculate_shared_wall_length(self, room1, room2):
        if not room1 or not room2: return 0
        ix1, iy1 = max(room1.x, room2.x), max(room1.y, room2.y)
        ix2, iy2 = min(room1.x + room1.w, room2.x + room2.w), min(room1.y + room1.h, room2.y + room2.h)
        return max(0, ix2 - ix1) + max(0, iy2 - iy1)

    # --- Simulated Annealing Core (Phase 1) ---
    def _get_random_neighbor_state(self, current_placed: List[PlacedRoom]) -> List[PlacedRoom] | None:
        new_placed = copy.deepcopy(current_placed)
        if not new_placed: return None

        # --- PHASE 2: Ensure we don't try to move 'fixed' rooms like corridors ---
        movable_rooms = [r for r in new_placed if not r.fixed]
        if len(movable_rooms) < 2: return None

        room_to_modify = random.choice(movable_rooms)
        anchor_room = random.choice([r for r in new_placed if r is not room_to_modify])
        
        candidates = []
        ax, ay, aw, ah = anchor_room.bbox()
        w, h = room_to_modify.w, room_to_modify.h
        
        for i in range(-w + 1, aw):
            candidates.append((ax + i, ay - h)); candidates.append((ax + i, ay + ah))
        for j in range(-h + 1, ah):
            candidates.append((ax - w, ay + j)); candidates.append((ax + aw, ay + j))
        
        random.shuffle(candidates)
        for x, y in candidates[:30]:
            if self._check_space_free_for_move(x, y, w, h, room_to_modify, new_placed):
                room_to_modify.x, room_to_modify.y = x, y
                return new_placed
        return None

    def _is_layout_valid(self, layout: List[PlacedRoom]) -> bool:
        for i, room in enumerate(layout):
            if room.x < 0 or room.y < 0 or room.x + room.w > self.grid.cols or room.y + room.h > self.grid.rows: return False
            for other_room in layout[i+1:]:
                if (room.x < other_room.x + other_room.w and room.x + room.w > other_room.x and
                    room.y < other_room.y + other_room.h and room.y + room.h > other_room.y): return False
        return True

    def _check_space_free_for_move(self, x, y, w, h, moving_room, all_rooms):
        if x<0 or y<0 or x+w>self.grid.cols or y+h>self.grid.rows: return False
        for room in all_rooms:
            if room is moving_room: continue
            if not (x + w <= room.x or x >= room.x + room.w or y + h <= room.y or y >= room.y + room.h): return False
        return True

    # --- SCORING ENGINE (UPGRADED FOR PHASE 2) ---
    def _evaluate_layout_score(self, layout: List[PlacedRoom], meta) -> float:
        if not self._is_layout_valid(layout): return -1e12

        total_score = 0
        
        # 1. Individual Room Scores (Proportions, Environment)
        for room in layout:
            total_score += self.score_room_properties(room)
        
        # 2. Global Scores (Rectangularity, Proximity)
        total_score += self._score_rectangularity(layout) * WEIGHT_RECTANGULARITY
        total_score += self._score_proximity(layout) * WEIGHT_PROXIMITY

        # 3. --- PHASE 2: Graph-Based Adjacency Score ---
        adj_graph = meta.get("adjacency_graph")
        if adj_graph:
            for r1, r2, data in adj_graph.edges(data=True):
                # Find the PlacedRoom objects corresponding to the names
                room1 = next((r for r in layout if r.name == r1), None)
                room2 = next((r for r in layout if r.name == r2), None)
                if not room1 or not room2: continue
                
                shared_len = self.calculate_shared_wall_length(room1, room2)
                rule = data.get('rule')
                
                if rule == 'must_be_adjacent':
                    if shared_len < ft_to_cells(4): total_score -= 10000 # Heavy penalty
                    else: total_score += 1000 # Reward
                elif rule == 'must_not_be_adjacent':
                    if shared_len > 0: total_score -= 10000 # Heavy penalty

        return total_score
    
    def _score_rectangularity(self, all_rooms: List[PlacedRoom]):
        if not all_rooms: return 0
        min_x = min(r.x for r in all_rooms); min_y = min(r.y for r in all_rooms)
        max_x = max(r.x + r.w for r in all_rooms); max_y = max(r.y + r.h for r in all_rooms)
        bbox_area = (max_x - min_x) * (max_y - min_y)
        if bbox_area == 0: return 0
        return (sum(r.w * r.h for r in all_rooms) / bbox_area) * 10.0

    def _score_proximity(self, layout: List[PlacedRoom]):
        """Scores how tightly packed the layout is."""
        if len(layout) < 2: return 0
        cx = sum(r.center()[0] for r in layout) / len(layout)
        cy = sum(r.center()[1] for r in layout) / len(layout)
        # Sum of squared distances from the centroid
        prox_score = sum((r.center()[0] - cx)**2 + (r.center()[1] - cy)**2 for r in layout)
        return -math.sqrt(prox_score) # Negative because we want to minimize distance

    def score_room_properties(self, room: PlacedRoom):
        score = 0
        # Environmental Score
        if room.spec.type in ("living", "master") and (room.y + room.h >= self.grid.rows):
            score += room.w * 1.5 * WEIGHT_ENVIRONMENTAL
        # Proportion Score
        aspect = max(room.w, room.h) / max(1, min(room.w, room.h))
        if aspect > 2.5: score += -10 * (aspect - 2.5) * WEIGHT_PROPORTIONS
        return score

    # === GENERATE METHOD (FIXED) ===
    def generate(self, specs, meta):
        # --- STEP 1: Place Fixed Rooms (Circulation Spine) ---
        initial_layout = []
        
        # Place Entrance
        entrance_spec = next((s for s in specs if s.type == 'entrance'), None)
        if entrance_spec:
            ew, eh = area_to_wh_cells(entrance_spec.area, self.cell_ft)
            ex, ey = self.grid.cols // 2 - ew // 2, self.grid.rows - eh
            entrance_room = PlacedRoom(entrance_spec, ex, ey, ew, eh, "public", fixed=True)
            initial_layout.append(entrance_room)

        # Place a single, consolidated Corridor
        corridor_spec = next((s for s in specs if s.type == 'corridor'), None)
        if corridor_spec:
            corr_h = ft_to_cells(DEFAULT_MIN_SIZES['corridor'][0], self.cell_ft)
            corr_w = self.grid.cols - (2 * self.grid_spacing_cells) # Make it wide
            corr_x = self.grid_spacing_cells
            corr_y = self.grid.rows // 2 - corr_h // 2
            corridor_room = PlacedRoom(corridor_spec, corr_x, corr_y, corr_w, corr_h, "public", fixed=True)
            initial_layout.append(corridor_room)

        # --- STEP 2: Initial Random Placement for Movable Rooms ---
        movable_specs = [s for s in specs if s.type not in ('entrance', 'corridor')]
        for spec in movable_specs:
            w, h = area_to_wh_cells(spec.area, self.cell_ft)
            placed_ok = False
            for _ in range(500): # Increased attempts
                x, y = random.randint(0, self.grid.cols - w), random.randint(0, self.grid.rows - h)
                
                # Check for overlap with already placed rooms
                is_overlap = any(
                    x < r.x + r.w and x + w > r.x and y < r.y + r.h and y + h > r.y
                    for r in initial_layout
                )
                if not is_overlap:
                    initial_layout.append(PlacedRoom(spec, x, y, w, h, zone=self.get_room_zone(spec.type)))
                    placed_ok = True
                    break
            
            if not placed_ok:
                print(f"ERROR: Failed to randomly place room: {spec.name}. The plot may be too crowded.")
                return False, f"Failed to perform initial random placement for {spec.name}", meta

        # --- STEP 3: Simulated Annealing Optimization ---
        current_solution = initial_layout
        current_score = self._evaluate_layout_score(current_solution, meta)
        T_initial, T_final, alpha = 1000.0, 1.0, 0.995
        T = T_initial
        
        print("Starting simulated annealing optimization...")
        for i in range(5000): # Using a fixed number of iterations can be more predictable
            if T <= T_final: break
            
            neighbor = self._get_random_neighbor_state(current_solution)
            if neighbor is None: continue

            neighbor_score = self._evaluate_layout_score(neighbor, meta)
            delta = neighbor_score - current_score
            
            if delta > 0 or random.random() < math.exp(delta / T):
                current_solution, current_score = neighbor, neighbor_score
            
            T *= alpha
            if i % 500 == 0: print(f"Iter: {i}, Temp: {T:.2f}, Score: {current_score:.2f}")

        # --- STEP 4: Finalize ---
        self.placed = current_solution
        self.occupied = [[None]*self.grid.rows for _ in range(self.grid.cols)]
        for r in self.placed:
            for i in range(r.x, r.x+r.w):
                for j in range(r.y, r.y+r.h): self.occupied[i][j] = r.name

        self._create_openings()
        print("Optimization complete.")
        return True, "Layout generated successfully via optimization.", meta

    # --- Rendering and Openings (Unchanged from Phase 1) ---
    def _create_openings(self):
        self.openings = []
        door_width = ft_to_cells(3, self.cell_ft)
        placed_bathrooms = self.get_rooms_by_type('bathroom', self.placed) + self.get_rooms_by_type('master_bathroom', self.placed)
        placed_bedrooms = self.get_rooms_by_type('bedroom', self.placed) + self.get_rooms_by_type('master', self.placed)
        
        def add_door(p1, p2, orientation):
            ix1, iy1 = p1.x, p1.y
            ix2, iy2 = p2.x, p2.y
            shared_wall_mid_x = (max(ix1, ix2) + min(ix1 + p1.w, ix2 + p2.w)) / 2
            shared_wall_mid_y = (max(iy1, iy2) + min(iy1 + p1.h, iy2 + p2.h)) / 2
            self.openings.append({'midpoint': (shared_wall_mid_x, shared_wall_mid_y), 'orientation': orientation})

        unassigned_baths = list(placed_bathrooms)
        for bath in placed_bathrooms:
            for bed in placed_bedrooms:
                if self.calculate_shared_wall_length(bath, bed) >= door_width:
                    orientation = 'h' if abs(bath.y - bed.y) > abs(bath.x - bed.x) else 'v'
                    add_door(bath, bed, orientation)
                    if bath in unassigned_baths: unassigned_baths.remove(bath)
                    break 

        corridor = next((r for r in self.placed if r.type == 'corridor'), None)
        if corridor:
            rooms_to_connect = (self.get_rooms_by_type('bedroom', self.placed) +
                                self.get_rooms_by_type('master', self.placed) +
                                self.get_rooms_by_type('living', self.placed))
            for room in rooms_to_connect:
                if self.calculate_shared_wall_length(room, corridor) >= door_width: add_door(room, corridor, 'h')
            for bath in unassigned_baths:
                 if self.calculate_shared_wall_length(bath, corridor) >= door_width: add_door(bath, corridor, 'h')

        kitchen = next((r for r in self.placed if r.type == 'kitchen'), None)
        if kitchen:
            for living in self.get_rooms_by_type('living', self.placed):
                if self.calculate_shared_wall_length(kitchen, living) >= door_width:
                    orientation = 'h' if abs(kitchen.y - living.y) > abs(kitchen.x - living.x) else 'v'
                    add_door(kitchen, living, orientation)
                    break
    
    def render_base_64(self, title="Floor Plan"):
        # This function is correct and does not need to be changed.
        cols, rows = self.grid.cols, self.grid.rows
        fig, ax = plt.subplots(figsize=(max(8, cols / 5), max(8, rows / 5)))
        colors = {"public": "#98FB98", "private": "#87CEEB", "service": "#FFA07A", "storage": "#DDDDDD"}

        for r in self.placed:
            rect = patches.Rectangle((r.x, r.y), r.w, r.h, facecolor=colors.get(r.zone, "#DDD"), edgecolor="gray", linewidth=0.8, alpha=0.9)
            ax.add_patch(rect)
            ax.text(r.x + r.w / 2, r.y + r.h / 2, f"{r.name}\n({r.area_sq_ft} sqft)", ha="center", va="center", fontsize=7, wrap=True)

        door_width_cells = ft_to_cells(3, self.cell_ft)
        for opening in self.openings:
            mx, my = opening['midpoint']
            if opening['orientation'] == 'h':
                p1, p2 = (mx - door_width_cells / 2, my), (mx + door_width_cells / 2, my)
            else:
                p1, p2 = (mx, my - door_width_cells / 2), (mx, my + door_width_cells / 2)
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color='white', linewidth=3.5, zorder=5)

        polygons = [Polygon([(r.x, r.y), (r.x + r.w, r.y), (r.x + r.w, r.y + r.h), (r.x, r.y + r.h)]) for r in self.placed]
        merged_shape = unary_union(polygons)
        
        if hasattr(merged_shape, 'exterior'):
             x, y = merged_shape.exterior.xy
             ax.plot(x, y, color='black', linewidth=3, solid_capstyle='round', zorder=10)
        if hasattr(merged_shape, 'geoms'):
            for geom in merged_shape.geoms:
                x, y = geom.exterior.xy
                ax.plot(x, y, color='black', linewidth=3, solid_capstyle='round', zorder=10)

        ent = next((r for r in self.placed if r.type == 'entrance'), None)
        if ent: ax.plot(ent.center()[0], ent.center()[1], 'o', color="red", markersize=8)
        ax.set_xlim(-2, cols + 2); ax.set_ylim(-2, rows + 2)
        ax.set_aspect("equal"); ax.axis("off")
        ax.set_title(title, fontsize=14, fontweight="bold")
        plt.gca().invert_yaxis()
        buf = io.BytesIO(); plt.savefig(buf, format='png', bbox_inches='tight'); plt.close(fig); buf.seek(0)
        return base64.b64encode(buf.getvalue()).decode('utf-8')  

# --- Adapter Function (UPGRADED FOR PHASE 2) ---
def generate_layout_from_constraints(constraints: Dict[str, Any]) -> Tuple[Dict[str, Any], Any]:
    lot = constraints.get("plot",{}); w,h = lot.get("width",0), lot.get("height",0)
    if not w or not h: return {"error": "Invalid plot dimensions."}, None
    
    specs = []
    room_constraints = constraints.get("rooms", []) or []
    
    # Intelligent Scaling Logic (Unchanged)
    plot_area = w * h; available_area = plot_area * MAX_AREA_COVERAGE_RATIO
    initial_specs = []; total_requested_area = 0
    for item in room_constraints:
        rtype_base = item.get("type", "other").lower()
        if "liv" in rtype_base or "din" in rtype_base: rtype = "living"
        elif "master" in rtype_base and "bath" in rtype_base: rtype = "master_bathroom"
        elif "master" in rtype_base: rtype = "master"
        elif "bed" in rtype_base: rtype = "bedroom"
        elif "bath" in rtype_base: rtype = "bathroom"
        elif "kitch" in rtype_base: rtype = "kitchen"
        elif "entran" in rtype_base: rtype = "entrance"
        else:
            # If not a core type, use its own name as the type
            # This makes the generator flexible to any new room type
            rtype = rtype_base
        count = int(item.get("count",1)); total_area_for_type = item.get("area", 100 * count)
        total_requested_area += total_area_for_type
        initial_specs.append({'type': rtype, 'count': count, 'total_area': total_area_for_type})
    if total_requested_area > available_area:
        guaranteed_area = 0
        for spec_info in initial_specs:
            min_dims = DEFAULT_MIN_SIZES.get(spec_info['type'], (5,5)); min_area = min_dims[0] * min_dims[1]
            spec_info['min_total_area'] = min_area * spec_info['count']; guaranteed_area += spec_info['min_total_area']
        if guaranteed_area > available_area:
            return {"error": f"Plot is too small. Minimum required area is {guaranteed_area:.0f} sqft, but only {available_area:.0f} is available."}, None
        remaining_area_to_distribute = available_area - guaranteed_area
        overage_area = total_requested_area - guaranteed_area
        for spec_info in initial_specs:
            proportion_of_overage = (spec_info['total_area'] - spec_info['min_total_area']) / overage_area if overage_area > 0 else 0
            final_total_area = spec_info['min_total_area'] + (remaining_area_to_distribute * proportion_of_overage)
            spec_info['final_area_per_room'] = final_total_area / spec_info['count']
    else:
        for spec_info in initial_specs: spec_info['final_area_per_room'] = spec_info['total_area'] / spec_info['count']
    
    # Create final RoomSpec objects
    room_counters = {}; specs = []
    for spec_info in initial_specs:
        rtype = spec_info['type']
        for _ in range(spec_info['count']):
            room_counters[rtype] = room_counters.get(rtype, 0) + 1
            name = f"{rtype.capitalize()} {room_counters[rtype]}"
            if rtype == "master": name = "Master Bedroom"
            if rtype == "entrance" and spec_info['count'] == 1: name = "Entrance"
            if rtype == "kitchen" and spec_info['count'] == 1: name = "Kitchen"
            specs.append(RoomSpec(name, rtype, spec_info['final_area_per_room']))

    # Add essentials
    if not any(s.type == 'entrance' for s in specs): specs.insert(0, RoomSpec("Entrance","entrance",40,priority=0))
    if not any(s.type == 'corridor' for s in specs): specs.append(RoomSpec("Corridor", "corridor", area_ft2=w*4))

    # --- PHASE 2, STEP 2: Build the Adjacency Graph ---
    adj_graph = nx.Graph()
    # Add nodes (all unique room names)
    for spec in specs: adj_graph.add_node(spec.name)
    
    # Define rules and add edges
    living_rooms = [s.name for s in specs if s.type == 'living']
    kitchens = [s.name for s in specs if s.type == 'kitchen']
    masters = [s.name for s in specs if s.type == 'master']
    bedrooms = [s.name for s in specs if s.type == 'bedroom']
    
    # Rule: Kitchen must be adjacent to a Living Room
    if kitchens and living_rooms:
        adj_graph.add_edge(kitchens[0], living_rooms[0], rule='must_be_adjacent')

    # Rule: Master bedroom must NOT be adjacent to noisy rooms
    for master_name in masters:
        for noisy_room in kitchens + living_rooms:
             adj_graph.add_edge(master_name, noisy_room, rule='must_not_be_adjacent')

    # --- Run Generator ---
    gen = FloorPlanGenerator(w,h)
    meta = {"entrance_side": "south", 
            "front_direction": "south", 
            "features": [],
            "adjacency_graph": adj_graph # Pass the graph to the generator
           }
    ok,msg,meta_out = gen.generate(specs, meta)
    
    return {
        "lot":lot,
        "features":gen.placed,
        "image_base_64":gen.render_base_64(),
        "status":"ok" if ok else "failed",
        "message":msg
    }, gen.placed