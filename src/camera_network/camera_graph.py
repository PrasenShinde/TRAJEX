"""
Camera Network Graph Module.

Represents the ANPR camera network as a directed graph using NetworkX.
Each node is a camera, each edge represents a plausible vehicle transition
with expected travel-time distributions.

This module is independent of synthetic data generation and can be reused
with real camera configurations.
"""

from typing import Dict, List, Optional, Tuple
import networkx as nx
import numpy as np
from config.settings import CameraConfig, DEFAULT_CAMERAS


class CameraGraph:
    """Directed graph representation of the ANPR camera network."""

    def __init__(self, camera_configs: Optional[List[Dict]] = None) -> None:
        """
        Build the camera graph from a list of camera configuration dicts.

        Args:
            camera_configs: List of camera config dicts matching CameraConfig fields.
                            Defaults to DEFAULT_CAMERAS from settings.
        """
        self.graph: nx.DiGraph = nx.DiGraph()
        self._cameras: Dict[str, CameraConfig] = {}

        configs = camera_configs or DEFAULT_CAMERAS
        self._build_graph(configs)

    def _build_graph(self, configs: List[Dict]) -> None:
        """Construct nodes and edges from configuration dicts."""
        for cfg in configs:
            cam = CameraConfig(
                camera_id=cfg["camera_id"],
                name=cfg["name"],
                latitude=cfg["latitude"],
                longitude=cfg["longitude"],
                entry_directions=cfg.get("entry_directions", []),
                exit_directions=cfg.get("exit_directions", []),
                connected_cameras=cfg.get("connected_cameras", []),
                travel_time_distributions=cfg.get("travel_time_distributions", {}),
                transition_probabilities=cfg.get("transition_probabilities", {}),
            )
            self._cameras[cam.camera_id] = cam

            self.graph.add_node(
                cam.camera_id,
                name=cam.name,
                latitude=cam.latitude,
                longitude=cam.longitude,
                entry_directions=cam.entry_directions,
                exit_directions=cam.exit_directions,
            )

        # Add directed edges
        for cam_id, cam in self._cameras.items():
            targets = [target for target in cam.connected_cameras if target in self._cameras]
            raw_probabilities = {
                target: max(0.0, float(cam.transition_probabilities.get(
                    target, 1.0 / len(targets) if targets else 0.0
                )))
                for target in targets
            }
            probability_total = sum(raw_probabilities.values())
            normalized_probabilities = (
                {target: value / probability_total for target, value in raw_probabilities.items()}
                if probability_total > 0 else
                {target: 1.0 / len(targets) for target in targets} if targets else {}
            )
            for target_id in targets:
                mean_tt, std_tt = cam.travel_time_distributions.get(
                    target_id, (300.0, 60.0)
                )
                self.graph.add_edge(
                    cam_id,
                    target_id,
                    mean_travel_time=mean_tt,
                    std_travel_time=std_tt,
                    transition_probability=normalized_probabilities[target_id],
                )

    # ── Query helpers ───────────────────────────────────────────────────

    def get_camera(self, camera_id: str) -> Optional[CameraConfig]:
        """Return the CameraConfig for a given camera ID."""
        return self._cameras.get(camera_id)

    def get_all_camera_ids(self) -> List[str]:
        """Return all camera IDs in insertion order."""
        return list(self._cameras.keys())

    def get_all_cameras(self) -> Dict[str, CameraConfig]:
        """Return the full camera dictionary."""
        return dict(self._cameras)

    def get_neighbours(self, camera_id: str) -> List[str]:
        """Return directly connected downstream camera IDs."""
        if camera_id not in self.graph:
            return []
        return list(self.graph.successors(camera_id))

    def are_directly_connected(self, cam_a: str, cam_b: str) -> bool:
        """Check whether a direct edge exists from cam_a to cam_b."""
        return self.graph.has_edge(cam_a, cam_b)

    def get_travel_time_distribution(
        self, cam_a: str, cam_b: str
    ) -> Optional[Tuple[float, float]]:
        """
        Return (mean_seconds, std_seconds) for the edge cam_a → cam_b.
        Returns None if no direct edge exists.
        """
        if not self.graph.has_edge(cam_a, cam_b):
            return None
        edge = self.graph.edges[cam_a, cam_b]
        return (edge["mean_travel_time"], edge["std_travel_time"])

    def get_transition_probability(self, cam_a: str, cam_b: str) -> Optional[float]:
        """Return the normalized prior probability for a directed camera edge."""
        if not self.graph.has_edge(cam_a, cam_b):
            return None
        return float(self.graph.edges[cam_a, cam_b]["transition_probability"])

    def shortest_path(self, cam_a: str, cam_b: str) -> Optional[List[str]]:
        """
        Return the shortest path (list of camera IDs) from cam_a to cam_b
        using hop count. Returns None if unreachable.
        """
        try:
            return nx.shortest_path(self.graph, cam_a, cam_b)
        except nx.NetworkXNoPath:
            return None

    def shortest_path_length(self, cam_a: str, cam_b: str) -> Optional[int]:
        """Return the hop count of the shortest path, or None if unreachable."""
        try:
            return nx.shortest_path_length(self.graph, cam_a, cam_b)
        except nx.NetworkXNoPath:
            return None

    def get_all_edges(self) -> List[Tuple[str, str, Dict]]:
        """Return all edges with their attributes."""
        return list(self.graph.edges(data=True))

    def expected_travel_time(
        self, cam_a: str, cam_b: str, rng: Optional[np.random.Generator] = None
    ) -> Optional[float]:
        """
        Sample a travel time for the direct edge cam_a → cam_b.
        Returns None if no direct edge exists.
        """
        dist = self.get_travel_time_distribution(cam_a, cam_b)
        if dist is None:
            return None
        mean, std = dist
        generator = rng or np.random.default_rng()
        # Clamp to positive
        return max(30.0, generator.normal(mean, std))

    def cumulative_expected_time(self, path: List[str]) -> float:
        """
        Return the sum of mean travel times along a multi-hop path.
        Raises ValueError if any edge is missing.
        """
        total = 0.0
        for i in range(len(path) - 1):
            dist = self.get_travel_time_distribution(path[i], path[i + 1])
            if dist is None:
                raise ValueError(
                    f"No direct edge from {path[i]} to {path[i+1]}"
                )
            total += dist[0]
        return total

    def get_camera_position(self, camera_id: str) -> Optional[Tuple[float, float]]:
        """Return (latitude, longitude) for a camera."""
        cam = self._cameras.get(camera_id)
        if cam is None:
            return None
        return (cam.latitude, cam.longitude)

    def num_cameras(self) -> int:
        """Return the number of cameras in the network."""
        return len(self._cameras)

    def num_edges(self) -> int:
        """Return the number of directed edges."""
        return self.graph.number_of_edges()

    def __repr__(self) -> str:
        return (
            f"CameraGraph(cameras={self.num_cameras()}, edges={self.num_edges()})"
        )
