"""
Vehicle Generator Module.

Creates synthetic vehicles with ground-truth attributes including:
- Unique vehicle IDs and number plates.
- Vehicle types and colours.
- Normalised appearance feature vectors (Re-ID embeddings).
- Routes through the hypothetical camera network.

Ground-truth identities are kept separate and are never exposed to the
association algorithm.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from config.settings import (
    SimulationSettings,
    VEHICLE_TYPES,
    VEHICLE_COLOURS,
    PLATE_PREFIXES,
)
from src.camera_network.camera_graph import CameraGraph


@dataclass
class Vehicle:
    """Ground-truth vehicle record."""
    vehicle_id: str
    number_plate: str
    vehicle_type: str
    colour: str
    embedding: np.ndarray            # Normalised Re-ID feature vector
    route: List[str]                 # Ordered list of camera IDs the vehicle visits
    route_timestamps: List[float]    # Absolute timestamps (epoch seconds) at each camera


class VehicleGenerator:
    """
    Generate a fleet of synthetic vehicles with ground-truth attributes
    and plausible routes through the camera network.
    """

    def __init__(
        self,
        camera_graph: CameraGraph,
        settings: Optional[SimulationSettings] = None,
    ) -> None:
        self.graph = camera_graph
        self.settings = settings or SimulationSettings()
        self.rng = np.random.default_rng(self.settings.random_seed)

    # ── Public API ──────────────────────────────────────────────────────

    def generate_vehicles(self) -> List[Vehicle]:
        """
        Generate *num_vehicles* synthetic vehicles, each with a random
        plausible route through the camera graph.
        """
        vehicles: List[Vehicle] = []
        appearance_templates: List[np.ndarray] = []
        camera_ids = self.graph.get_all_camera_ids()

        for idx in range(self.settings.num_vehicles):
            vid = f"V-{idx+1:04d}"
            plate = self._generate_plate()
            vtype = self.rng.choice(VEHICLE_TYPES)
            colour = self.rng.choice(VEHICLE_COLOURS)
            if (
                appearance_templates
                and self.rng.random() < self.settings.similar_appearance_rate
            ):
                template = appearance_templates[int(self.rng.integers(0, len(appearance_templates)))]
                embedding = self._generate_similar_embedding(template)
            else:
                embedding = self._generate_embedding()
            appearance_templates.append(embedding)
            route = self._generate_route(camera_ids)
            timestamps = self._generate_timestamps(route)

            vehicles.append(Vehicle(
                vehicle_id=vid,
                number_plate=plate,
                vehicle_type=vtype,
                colour=colour,
                embedding=embedding,
                route=route,
                route_timestamps=timestamps,
            ))

        return vehicles

    def vehicles_to_dataframe(self, vehicles: List[Vehicle]) -> pd.DataFrame:
        """Convert list of Vehicle objects to a Pandas DataFrame (no embeddings)."""
        rows = []
        for v in vehicles:
            rows.append({
                "vehicle_id": v.vehicle_id,
                "number_plate": v.number_plate,
                "vehicle_type": v.vehicle_type,
                "colour": v.colour,
                "route": v.route,
                "route_length": len(v.route),
            })
        return pd.DataFrame(rows)

    # ── Private helpers ─────────────────────────────────────────────────

    def _generate_plate(self) -> str:
        """Generate a random Indian-style number plate string."""
        prefix = self.rng.choice(PLATE_PREFIXES)
        digits_1 = self.rng.integers(1, 100)
        letters = "".join(self.rng.choice(list("ABCDEFGHJKLMNPQRSTUVWXYZ"), size=2))
        digits_2 = self.rng.integers(1000, 10000)
        return f"{prefix}{digits_1:02d}{letters}{digits_2}"

    def _generate_embedding(self) -> np.ndarray:
        """Generate a normalised random embedding vector."""
        dim = self.settings.embedding_dim
        vec = self.rng.normal(0, 1, size=dim).astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    def _generate_similar_embedding(self, template: np.ndarray) -> np.ndarray:
        """Create a distinct vehicle embedding near another appearance template."""
        vec = template + self.rng.normal(0.0, 0.06, size=template.shape)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec.astype(np.float32)

    def _generate_route(self, camera_ids: List[str]) -> List[str]:
        """
        Generate a plausible route by performing a random walk on the
        camera graph.  Falls back to a random subset if the graph is
        disconnected or the walk is too short.
        """
        route_len = self.rng.integers(
            self.settings.min_route_length,
            self.settings.max_route_length + 1,
        )
        # Start at a camera that has an outbound road connection. Starting
        # at a sink (for example the south exit) would otherwise produce a
        # one-camera route and require inventing a non-graph transition.
        start_candidates = [cam_id for cam_id in camera_ids if self.graph.get_neighbours(cam_id)]
        if not start_candidates:
            return [self.rng.choice(camera_ids)]
        start = self.rng.choice(start_candidates)
        route = [start]

        for _ in range(route_len - 1):
            neighbours = self.graph.get_neighbours(route[-1])
            if not neighbours:
                break
            next_cam = self.rng.choice(neighbours)
            route.append(next_cam)

        # Do not pad a short walk with arbitrary cameras: every consecutive
        # pair must remain a real directed edge in the camera graph.
        return route

    def _generate_timestamps(self, route: List[str]) -> List[float]:
        """
        Generate monotonically increasing timestamps along the route.
        The first timestamp is drawn from the simulation window; subsequent
        ones are offset by sampled travel times.
        """
        duration_secs = self.settings.simulation_duration_hours * 3600
        # Start at a random point in the first 80 % of the window
        start_time = self.rng.uniform(0, duration_secs * 0.8)
        timestamps = [start_time]

        for i in range(1, len(route)):
            tt = self.graph.expected_travel_time(route[i - 1], route[i], self.rng)
            if tt is None:
                # No direct edge — use a fallback travel time
                tt = self.rng.uniform(120, 600)
            timestamps.append(timestamps[-1] + tt)

        return timestamps
