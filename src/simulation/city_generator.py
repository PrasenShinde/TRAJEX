"""
City Generator Module.

Provides a convenience wrapper that constructs the full SmartCity
simulation environment: camera graph, default or custom camera
configurations, and city metadata.
"""

from copy import deepcopy
from typing import Dict, List, Optional
from config.settings import DEFAULT_CAMERAS, SimulationSettings
from src.camera_network.camera_graph import CameraGraph


class CityGenerator:
    """
    Generates the SmartCity environment with configurable camera layouts.
    """

    def __init__(
        self,
        settings: Optional[SimulationSettings] = None,
        custom_cameras: Optional[List[Dict]] = None,
    ) -> None:
        self.settings = settings or SimulationSettings()
        self._camera_configs = (
            deepcopy(custom_cameras)
            if custom_cameras is not None
            else self._build_default_layout(self.settings.num_cameras)
        )
        self.city_name = "SmartCity"
        self.camera_graph: Optional[CameraGraph] = None

    @staticmethod
    def _build_default_layout(num_cameras: int) -> List[Dict]:
        """Create a graph-constrained layout with the requested camera count.

        Counts from 4 through 8 use a connected subset of the hand-designed
        SmartCity layout. Additional cameras extend the southbound corridor.
        """
        if not 4 <= num_cameras <= 16:
            raise ValueError("SmartCity supports between 4 and 16 cameras.")

        cameras = deepcopy(DEFAULT_CAMERAS[:min(num_cameras, len(DEFAULT_CAMERAS))])
        if num_cameras <= len(DEFAULT_CAMERAS):
            selected_ids = {camera["camera_id"] for camera in cameras}
            for camera in cameras:
                camera["connected_cameras"] = [
                    target for target in camera["connected_cameras"]
                    if target in selected_ids
                ]
                camera["travel_time_distributions"] = {
                    target: distribution
                    for target, distribution in camera["travel_time_distributions"].items()
                    if target in selected_ids
                }
            return cameras

        # CAM-07 branches toward the existing CAM-08 exit and this added
        # southbound corridor. Each generated node connects only to its next
        # neighbour, keeping the directed topology sparse and understandable.
        cam_07 = next(camera for camera in cameras if camera["camera_id"] == "CAM-07")
        cam_07["connected_cameras"].append("CAM-09")
        cam_07["travel_time_distributions"]["CAM-09"] = (260, 55)

        for index in range(9, num_cameras + 1):
            camera_id = f"CAM-{index:02d}"
            next_id = f"CAM-{index + 1:02d}" if index < num_cameras else None
            camera = {
                "camera_id": camera_id,
                "name": f"South Corridor Junction {index - 8}",
                "latitude": 28.634 - 0.002 * (index - 8),
                "longitude": 77.229 + 0.001 * ((index - 8) % 3),
                "entry_directions": ["N", "NW"],
                "exit_directions": ["S", "SE"],
                "connected_cameras": [next_id] if next_id else [],
                "travel_time_distributions": {next_id: (240, 50)} if next_id else {},
            }
            cameras.append(camera)
        return cameras

    def build(self) -> CameraGraph:
        """
        Construct and return the camera graph.
        """
        self.camera_graph = CameraGraph(self._camera_configs)
        return self.camera_graph

    def get_city_metadata(self) -> Dict:
        """Return summary metadata about the city."""
        return {
            "city_name": self.city_name,
            "num_cameras": len(self._camera_configs),
            "camera_ids": [c["camera_id"] for c in self._camera_configs],
            "center_lat": sum(c["latitude"] for c in self._camera_configs) / len(self._camera_configs),
            "center_lon": sum(c["longitude"] for c in self._camera_configs) / len(self._camera_configs),
        }
