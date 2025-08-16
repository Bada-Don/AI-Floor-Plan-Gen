# floorplan/generator.py
import math, random, io, base64, itertools, copy, heapq
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from collections import deque, namedtuple
from typing import Dict, Any, List, Tuple

# --- PHASE 3: New Dependencies ---
import networkx as nx
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union
from shapely.affinity import scale, translate
from scipy.spatial import Voronoi
from descartes import PolygonPatch
import scipy # --- FIX: Required for catching specific QhullError ---

import matplotlib.patches as mpatches


# === Architectural Rules & Constants (Phase 3) ===
WEIGHT_ADJACENCY = 80.0
WEIGHT_AREA_MATCH = 100.0
WEIGHT_COMPACTNESS = 20.0
WEIGHT_PROPORTIONS = 5.0
WEIGHT_RECTANGULARITY = 18.0
GRID_SPACING_FT = 4
DEFAULT_MIN_SIZES = { "bedroom": (8, 9), "master": (12, 12), "bathroom": (5, 7), "kitchen": (8, 10), "living": (10, 12), "entrance": (5, 5), "corridor": (4, 20)}
MAX_AREA_COVERAGE_RATIO = 0.80

# === Core Definitions (Phase 3: Geometry-based) ===
def ft_to_units(dim_ft, cell_ft=1): return dim_ft / cell_ft

def ft2_to_units2(area_ft2, cell_ft=1):
    return area_ft2 / (cell_ft * cell_ft)

class Grid:
    def __init__(self, width, height):
        self.width, self.height = width, height

class RoomSpec:
    def __init__(self, name, room_type, area_ft2=None, prefs=None, priority=5):
        self.name, self.type, self.area, self.prefs, self.priority = name, room_type, area_ft2, prefs or {}, priority

class PlacedRoom:
    def __init__(self, spec: RoomSpec, polygon: Polygon, zone="private"):
        self.spec, self.name, self.type, self.polygon, self.zone = spec, spec.name, spec.type, polygon, zone

    @property
    def area(self):
        if self.polygon and isinstance(self.polygon, Polygon):
            return self.polygon.area
        return 0

    def center(self):
        if self.polygon and not self.polygon.is_empty:
            return self.polygon.centroid.coords[0]
        return (0, 0)

class FloorPlanGenerator:
    def __init__(self, plot_w_ft, plot_h_ft, cell_ft=1, verbose=False):
        self.grid = Grid(plot_w_ft, plot_h_ft)
        self.cell_ft = cell_ft; self.placed = []; self.verbose = verbose
        self.boundary = Polygon([(0, 0), (self.grid.width, 0), (self.grid.width, self.grid.height), (0, self.grid.height)])
        self.openings = []

    def get_room_by_name(self, name: str, layout: List[PlacedRoom]) -> PlacedRoom | None:
        return next((r for r in layout if r.name == name), None)

    def get_shared_wall(self, room1: PlacedRoom, room2: PlacedRoom) -> LineString | None:
        if not all([room1.polygon, room2.polygon, isinstance(room1.polygon, Polygon), isinstance(room2.polygon, Polygon)]):
            return None
        if not room1.polygon.touches(room2.polygon): return None
        intersection = room1.polygon.intersection(room2.polygon)
        if isinstance(intersection, LineString): return intersection
        return None
        # Add this to the validation function to see what's wrong
    def debug_polygon_structure(self, polygon, name):
        try:
            coords = list(polygon.exterior.coords)
            print(f"DEBUG {name}: {len(coords)} coords")
            for i, coord in enumerate(coords[:3]):  # Show first 3
                print(f"  Coord {i}: {coord} (type: {type(coord)}, len: {len(coord) if hasattr(coord, '__len__') else 'N/A'})")
        except Exception as e:
            print(f"DEBUG {name}: Failed to debug - {e}")
    
    def _validate_polygon_for_rendering(self, polygon: Polygon, room_name: str = "Unknown") -> bool:
        """
        Deep validation to ensure polygon can be rendered by descartes/matplotlib
        """
        try:
            # Basic checks
            if not isinstance(polygon, Polygon) or polygon.is_empty or not polygon.is_valid:
                return False
            
            if polygon.area < 1.0:
                return False
            
            # Check exterior coordinates
            if not hasattr(polygon, 'exterior'):
                return False
            
            coords = polygon.exterior.coords
            
            # Check if coords is accessible
            try:
                coord_list = list(coords)
                if len(coord_list) < 4:
                    print(f"Insufficient coordinates for {room_name}: {len(coord_list)}")
                    return False
                # Ensure every item is a 2-element sequence
                for i, coord in enumerate(coord_list):
                    if not isinstance(coord, (tuple, list)) or len(coord) < 2:
                        print(f"Bad coord at {i} in {room_name}: {coord}")
                        return False
            except Exception as e:
                print(f"Cannot convert coords to list for {room_name}: {e}")
                return False
            
            if len(coord_list) < 4:
                print(f"Insufficient coordinates for {room_name}: {len(coord_list)}")
                return False
            
            # Validate each coordinate
            for i, coord in enumerate(coord_list):
                try:
                    if len(coord) < 2:
                        print(f"Invalid coordinate {i} for {room_name}: {coord}")
                        return False
                    
                    x, y = coord[0], coord[1]
                    if not (isinstance(x, (int, float)) and isinstance(y, (int, float))):
                        print(f"Non-numeric coordinates for {room_name}: {coord}")
                        return False
                    
                    if not (math.isfinite(x) and math.isfinite(y)):
                        print(f"Non-finite coordinates for {room_name}: {coord}")
                        return False
                        
                except Exception as e:
                    print(f"Error validating coordinate {i} for {room_name}: {e}")
                    return False
            
            # Test if descartes can handle it by creating a numpy array (this is what fails)
            try:
                import numpy as np
                coords_array = np.atleast_2d(np.asarray(coord_list))
                if coords_array.shape[0] < 4 or coords_array.shape[1] < 2:
                    print(f"Invalid coordinate array for {room_name}: shape={coords_array.shape}")
                    return False

                    
                # Test the specific operation that's failing in descartes
                test_slice = coords_array[:, :2]  # This is the operation that fails
                if test_slice.size == 0:
                    print(f"Empty coordinate slice for {room_name}")
                    return False
                    
            except Exception as e:
                print(f"Numpy validation failed for {room_name}: {e}")
                return False
            
            return True
            
        except Exception as e:
            print(f"General validation failed for {room_name}: {e}")
            return False

    def _create_voronoi_layout(self, specs: List[RoomSpec]) -> List[PlacedRoom]:
        num_rooms = len(specs)
        
        for attempt in range(10):
            try:
                # Generate more spread-out points
                points = []
                for i in range(num_rooms):
                    x = random.uniform(self.grid.width * 0.1, self.grid.width * 0.9)
                    y = random.uniform(self.grid.height * 0.1, self.grid.height * 0.9)
                    points.append(Point(x, y))
                
                # Add some boundary points for better tessellation
                for _ in range(max(10, num_rooms)):
                    x = random.uniform(1, self.grid.width-1)
                    y = random.uniform(1, self.grid.height-1)
                    points.append(Point(x, y))

                vor = Voronoi([p.coords[0] for p in points])
                
                regions = []
                for region_indices in vor.regions:
                    if not region_indices or -1 in region_indices: continue
                    try:
                        poly = Polygon([vor.vertices[i] for i in region_indices])
                        if not poly.is_valid: poly = poly.buffer(0)
                        clipped_poly = poly.intersection(self.boundary)
                        
                        if (isinstance(clipped_poly, Polygon) and 
                            clipped_poly.is_valid and 
                            not clipped_poly.is_empty and 
                            clipped_poly.area > 10.0):  # Minimum area check
                            regions.append(clipped_poly)
                    except Exception:
                        continue

                if len(regions) >= num_rooms:
                    break
            except Exception as e:
                print(f"Voronoi attempt {attempt + 1} failed: {e}")
                continue
        else:
            raise RuntimeError("Failed to generate enough valid Voronoi regions")

        # Rest of the method...
        regions.sort(key=lambda p: p.area, reverse=True)
        selected_regions = regions[:num_rooms]
        specs.sort(key=lambda s: s.area, reverse=True)
        
        initial_layout = []
        for i, spec in enumerate(specs):
            poly = selected_regions[i]
            
            # More conservative scaling
            target_area = spec.area
            current_area = poly.area
            scale_factor = math.sqrt(target_area / current_area) if current_area > 0 else 1.0
            scale_factor = max(0.5, min(2.0, scale_factor))  # Limit scaling
            
            scaled_poly = scale(poly, xfact=scale_factor, yfact=scale_factor, origin=poly.centroid)
            scaled_poly = scaled_poly.intersection(self.boundary)

            final_poly = scaled_poly if isinstance(scaled_poly, Polygon) and not scaled_poly.is_empty else poly
            
            # Validate final polygon
            if final_poly.area < 5.0:
                print(f"Warning: Room {spec.name} has very small area: {final_poly.area}")
            
            zone = self.get_room_zone(spec.type)
            initial_layout.append(PlacedRoom(spec, final_poly, zone))

        return initial_layout
    def _get_random_neighbor_state(self, current_placed: List[PlacedRoom]) -> List[PlacedRoom] | None:
        new_placed = copy.deepcopy(current_placed)
        if not new_placed: return None

        room_to_modify = random.choice(new_placed)
        original_poly = room_to_modify.polygon
        if not isinstance(original_poly, Polygon): return None

        move_type = random.choice(['translate', 'scale', 'move_vertex'])

        new_poly = None
        if move_type == 'translate':
            dx = random.uniform(-self.grid.width * 0.05, self.grid.width * 0.05)
            dy = random.uniform(-self.grid.height * 0.05, self.grid.height * 0.05)
            new_poly = translate(original_poly, dx, dy)

        elif move_type == 'scale':
            factor = random.uniform(0.9, 1.1)
            new_poly = scale(original_poly, xfact=factor, yfact=factor, origin='centroid')

        elif move_type == 'move_vertex' and len(original_poly.exterior.coords) > 3:
            coords = list(original_poly.exterior.coords)
            v_index = random.randint(0, len(coords) - 2)
            vx, vy = coords[v_index]
            dx = random.uniform(-self.grid.width * 0.03, self.grid.width * 0.03)
            dy = random.uniform(-self.grid.height * 0.03, self.grid.height * 0.03)
            coords[v_index] = (vx + dx, vy + dy)
            if v_index == 0: coords[-1] = coords[0]
            try:
                new_poly = Polygon(coords)
            except Exception:
                return None

        if not new_poly: return None

        # CRITICAL: Validate the new polygon immediately
        if not new_poly.is_valid:
            new_poly = new_poly.buffer(0)
            if new_poly.is_empty or new_poly.geom_type != 'Polygon': 
                return None
        
        # Check minimum area to prevent degenerate polygons
        if new_poly.area < 10.0:  # Minimum area threshold
            return None
        
        # Validate coordinates are accessible
        try:
            coords = list(new_poly.exterior.coords)
            if len(coords) < 4 or not all(len(coord) >= 2 for coord in coords):
                return None
        except (AttributeError, IndexError, TypeError):
            return None

        room_to_modify.polygon = new_poly.intersection(self.boundary)
        
        # Final validation after boundary intersection
        if (not isinstance(room_to_modify.polygon, Polygon) or 
            room_to_modify.polygon.is_empty or 
            room_to_modify.polygon.area < 5.0):
            return None

        # Rest of collision detection code...
        for _ in range(3):
            had_collision = False
            for other_room in new_placed:
                if other_room.name == room_to_modify.name: continue
                if not isinstance(other_room.polygon, Polygon): continue

                if room_to_modify.polygon.intersects(other_room.polygon):
                    if room_to_modify.polygon.intersection(other_room.polygon).area > 1e-2:
                        had_collision = True
                        c1 = room_to_modify.polygon.centroid; c2 = other_room.polygon.centroid
                        dx, dy = c1.x - c2.x, c1.y - c2.y
                        dist = math.sqrt(dx**2 + dy**2)
                        if dist > 1e-5:
                            move_vec_x = (dx / dist) * 0.5
                            move_vec_y = (dy / dist) * 0.5
                            room_to_modify.polygon = translate(room_to_modify.polygon, move_vec_x, move_vec_y)
            if not had_collision:
                break

        room_to_modify.polygon = room_to_modify.polygon.intersection(self.boundary)

        # Final validation
        if (isinstance(room_to_modify.polygon, Polygon) and 
            not room_to_modify.polygon.is_empty and 
            room_to_modify.polygon.area >= 5.0):
            return new_placed

        return None

    def _is_layout_valid(self, layout: List[PlacedRoom]) -> bool:
        for r1, r2 in itertools.combinations(layout, 2):
            if not (r1.polygon and r2.polygon and isinstance(r1.polygon, Polygon) and isinstance(r2.polygon, Polygon)):
                return False
            if r1.polygon.intersects(r2.polygon):
                if r1.polygon.intersection(r2.polygon).area > 1e-2:
                    return False
        return True

    def _evaluate_layout_score(self, layout: List[PlacedRoom], meta) -> float:
        if not self._is_layout_valid(layout): 
            return -1e6  # Less extreme penalty
        
        total_score = 1000  # Start with a positive base score
        
        for room in layout:
            if room.area <= 0:
                return -1e6  # Invalid room
                
            # Area matching (less harsh penalty)
            area_mismatch = abs(room.area - room.spec.area) / room.spec.area
            total_score -= area_mismatch * WEIGHT_AREA_MATCH * 0.5  # Reduce weight
            
            # Compactness
            if room.area > 0:
                compactness_ratio = (room.polygon.length ** 2) / room.area
                total_score -= (compactness_ratio / 100.0) * WEIGHT_COMPACTNESS  # Adjust divisor
        
        # Adjacency scoring (existing code)
        adj_graph = meta.get("adjacency_graph")
        if adj_graph:
            for r1_name, r2_name, data in adj_graph.edges(data=True):
                room1 = self.get_room_by_name(r1_name, layout)
                room2 = self.get_room_by_name(r2_name, layout)
                if not room1 or not room2: continue
                
                shared_wall = self.get_shared_wall(room1, room2)
                rule = data.get('rule')
                
                if rule == 'must_be_adjacent':
                    if shared_wall and shared_wall.length > ft_to_units(4):
                        total_score += (shared_wall.length / self.grid.width) * 10 * WEIGHT_ADJACENCY
                    else:
                        total_score -= 0.5 * WEIGHT_ADJACENCY  # Less harsh penalty
                elif rule == 'must_not_be_adjacent':
                    if shared_wall: 
                        total_score -= 0.75 * WEIGHT_ADJACENCY  # Less harsh penalty

        # Rectangularity bonus (existing code but with validation)
        valid_polygons = []
        for r in layout:
            if isinstance(r.polygon, Polygon) and r.polygon.area > 0:
                valid_polygons.append(r.polygon)
        
        if valid_polygons:
            try:
                union_shape = unary_union(valid_polygons)
                total_area = sum(p.area for p in valid_polygons)
                if total_area > 0:
                    bounding_box_area = union_shape.envelope.area
                    rect_score = total_area / bounding_box_area if bounding_box_area > 0 else 0
                    total_score += rect_score * WEIGHT_RECTANGULARITY
            except Exception:
                pass  # Skip if union fails
        
        return total_score

    def get_rooms_by_type(self, rtype, layout: List[PlacedRoom]):
        return [r for r in layout if r.type == rtype]

    def get_room_zone(self, rtype):
        if rtype in ("living", "entrance", "corridor"): return "public"
        if rtype == "kitchen": return "service"
        return "private"

    def _finalize_and_clean_layout(self, layout: List[PlacedRoom]) -> List[PlacedRoom]:
        cleaned_layout = []
        for room in layout:
            poly = room.polygon

            if not poly or poly.is_empty:
                print(f"Warning: Discarding room '{room.name}' due to empty geometry.")
                continue

            if not poly.is_valid:
                poly = poly.buffer(0)

            if poly.is_empty:
                print(f"Warning: Discarding room '{room.name}' as it became empty after fixing.")
                continue

            if poly.geom_type == 'MultiPolygon':
                poly = max(poly.geoms, key=lambda p: p.area)

            if poly.geom_type not in ["Polygon", "MultiPolygon"]:
                print(f"Warning: Discarding room '{room.name}' - invalid geom_type {poly.geom_type}")
                continue


            # Use the enhanced validation
            if not self._validate_polygon_for_rendering(poly, room.name):
                print(f"Warning: Discarding room '{room.name}' - failed rendering validation.")
                continue

            room.polygon = poly
            cleaned_layout.append(room)

        return cleaned_layout

    def generate(self, specs, meta):
        try:
            initial_layout = self._create_voronoi_layout(specs)
        except RuntimeError as e:
            return False, str(e), meta

        current_solution = initial_layout
        current_score = self._evaluate_layout_score(current_solution, meta)
        T_initial, T_final, alpha = 500.0, 0.1, 0.998
        T = T_initial

        print("Starting geometric optimization...")
        try:
            for i in range(20000):
                if T <= T_final: break
                neighbor = self._get_random_neighbor_state(current_solution)
                if neighbor is None: continue
                neighbor_score = self._evaluate_layout_score(neighbor, meta)
                delta = neighbor_score - current_score
                if delta > 0 or random.random() < math.exp(delta / T):
                    current_solution, current_score = neighbor, neighbor_score
                T *= alpha
                if i % 1000 == 0: print(f"Iter: {i}, Temp: {T:.2f}, Score: {current_score:.2f}")
        except Exception as e:
            print(f"Error during optimization: {e}. Proceeding with last valid solution.")

        print("Optimization complete. Cleaning final layout...")
        self.placed = self._finalize_and_clean_layout(current_solution)
        self._create_openings()
        print("Layout finalized.")
        return True, "Layout generated successfully via geometric optimization.", meta

    def _create_openings(self):
        self.openings = []
        door_width = ft_to_units(3, self.cell_ft)

        for r1, r2 in itertools.combinations(self.placed, 2):
            connect_exceptions = [('bedroom', 'bedroom'), ('master','bedroom')]
            if (r1.type, r2.type) in connect_exceptions or (r2.type, r1.type) in connect_exceptions:
                continue

            shared_wall = self.get_shared_wall(r1, r2)
            if shared_wall and shared_wall.is_valid and shared_wall.length >= door_width:
                midpoint = shared_wall.centroid
                dx = abs(shared_wall.coords[0][0] - shared_wall.coords[-1][0])
                dy = abs(shared_wall.coords[0][1] - shared_wall.coords[-1][1])
                orientation = 'h' if dx > dy else 'v'
                self.openings.append({'midpoint': midpoint.coords[0], 'orientation': orientation})

    def render_base_64(self, title="Floor Plan"):
        fig, ax = plt.subplots(figsize=(max(8, self.grid.width / 5), max(8, self.grid.height / 5)))
        colors = {"public": "#98FB98", "private": "#87CEEB", "service": "#FFA07A", "storage": "#DDDDDD"}

        for r in self.placed:
            poly = r.polygon
            if not isinstance(poly, Polygon):
                print(f"Skipping {r.name} - geometry type {poly.geom_type}")
                continue
            if not self._validate_polygon_for_rendering(poly, r.name):
                print(f"Skipping rendering for room '{r.name}' - failed validation.")
                continue

            try:
                # Convert Shapely polygon to matplotlib-compatible coordinates
                coords = list(poly.exterior.coords)
                if len(coords) < 4:
                    print(f"Skipping {r.name} - insufficient coordinates")
                    continue
                
                # Create matplotlib Polygon patch directly
                patch = mpatches.Polygon(coords, 
                                    facecolor=colors.get(r.zone, "#DDD"),
                                    edgecolor="gray", 
                                    linewidth=0.8, 
                                    alpha=0.9)
                ax.add_patch(patch)
                
                center = r.center()
                ax.text(center[0], center[1], f"{r.name}\n({r.area:.0f} sqft)",
                        ha="center", va="center", fontsize=7, wrap=True)
            except Exception as e:
                print(f"CRITICAL: Failed to render room '{r.name}' after fix attempt. Error: {e}")
                continue

        # Fix door rendering...
        door_width_units = ft_to_units(3, self.cell_ft)
        for opening in self.openings:
            mx, my = opening['midpoint']
            if opening['orientation'] == 'h':
                p1, p2 = (mx - door_width_units / 2, my), (mx + door_width_units / 2, my)
            else:
                p1, p2 = (mx, my - door_width_units / 2), (mx, my + door_width_units / 2)
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color='white', linewidth=3.5, zorder=5)

        # Fix merged shape rendering
        valid_polygons = []
        for r in self.placed:
            if isinstance(r.polygon, Polygon) and not r.polygon.is_empty:
                valid_polygons.append(r.polygon)

        if valid_polygons:
            try:
                merged_shape = unary_union(valid_polygons)
                if merged_shape.is_valid and not merged_shape.is_empty:
                    if merged_shape.geom_type == 'Polygon':
                        try:
                            coords = list(merged_shape.exterior.coords)
                            patch = mpatches.Polygon(coords, facecolor='none', 
                                                edgecolor='black', linewidth=3, zorder=10)
                            ax.add_patch(patch)
                        except Exception as e:
                            print(f"Failed to render merged shape outline: {e}")
                            
                    elif merged_shape.geom_type == 'MultiPolygon':
                        for i, poly in enumerate(merged_shape.geoms):
                            try:
                                coords = list(poly.exterior.coords)
                                patch = mpatches.Polygon(coords, facecolor='none', 
                                                    edgecolor='black', linewidth=3, zorder=10)
                                ax.add_patch(patch)
                            except Exception as e:
                                print(f"Failed to render polygon {i} in MultiPolygon outline: {e}")
                                continue
            except Exception as e:
                print(f"Failed to create or render merged shape: {e}")

        # Rest of your rendering code...
        ent = next((r for r in self.placed if r.type == 'entrance'), None)
        if ent:
            try:
                center = ent.center()
                if center and len(center) >= 2:
                    ax.plot(center[0], center[1], 'o', color="red", markersize=8)
            except Exception as e:
                print(f"Failed to render entrance marker: {e}")

        ax.set_xlim(-2, self.grid.width + 2)
        ax.set_ylim(-2, self.grid.height + 2)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(title, fontsize=14, fontweight="bold")
        plt.gca().invert_yaxis()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.getvalue()).decode('utf-8')

def generate_layout_from_constraints(constraints: Dict[str, Any]) -> Tuple[Dict[str, Any], Any]:
    lot = constraints.get("plot",{}); w,h = lot.get("width",0), lot.get("height",0)
    if not w or not h: return {"error": "Invalid plot dimensions."}, None
    room_constraints = constraints.get("rooms", []) or []
    if not room_constraints:
        return {"error": "No rooms specified in the constraints."}, None
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
        else: rtype = rtype_base
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
    room_counters = {}; specs = []
    for spec_info in initial_specs:
        rtype = spec_info['type']
        for _ in range(spec_info['count']):
            room_counters[rtype] = room_counters.get(rtype, 0) + 1
            name = f"{rtype.replace('_',' ').title()} {room_counters[rtype]}"
            if rtype == "master": name = "Master Bedroom"
            if rtype == "entrance" and spec_info['count'] == 1: name = "Entrance"
            if rtype == "kitchen" and spec_info['count'] == 1: name = "Kitchen"
            area_in_units = ft2_to_units2(spec_info['final_area_per_room'], cell_ft=1)
            specs.append(RoomSpec(name, rtype, area_in_units))
    if not any(s.type == 'entrance' for s in specs): specs.insert(0, RoomSpec("Entrance","entrance",40,priority=0))
    adj_graph = nx.Graph()
    for spec in specs: adj_graph.add_node(spec.name)
    living_rooms = [s.name for s in specs if s.type == 'living']
    kitchens = [s.name for s in specs if s.type == 'kitchen']
    masters = [s.name for s in specs if s.type == 'master']
    if kitchens and living_rooms:
        adj_graph.add_edge(kitchens[0], living_rooms[0], rule='must_be_adjacent')
    for master_name in masters:
        for noisy_room in kitchens + living_rooms:
             adj_graph.add_edge(master_name, noisy_room, rule='must_not_be_adjacent')
    gen = FloorPlanGenerator(w,h)
    meta = {"entrance_side": "south", "front_direction": "south", "features": [], "adjacency_graph": adj_graph}
    ok,msg,meta_out = gen.generate(specs, meta)
    features_list = []
    for room in gen.placed:
        features_list.append({
            "name": room.name,
            "type": room.type,
            "zone": room.zone,
            "area": room.area,
            "polygon_coords": list(room.polygon.exterior.coords)
        })
    return {
        "lot": lot,
        "features": features_list,
        "image_base_64": gen.render_base_64(),
        "status": "ok" if ok else "failed",
        "message": msg
    }, gen.placed