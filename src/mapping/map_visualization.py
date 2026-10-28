"""
Map Visualization Module.

Renders interactive Folium maps showing:
- Camera locations and IDs.
- Camera-to-camera graph connections.
- Selected vehicle trajectories with direction of movement.
- Observed vs inferred vs uncertain segments.

Uses OpenStreetMap tiles.  If OSM is unavailable, falls back to a
simple HTML-based hypothetical map.
"""

from typing import Dict, List, Optional, Tuple
import folium
from folium import plugins
import numpy as np

from src.camera_network.camera_graph import CameraGraph
from src.trajectory.trajectory_reconstruction import (
    ReconstructedTrajectory,
    TrajectorySegment,
)
from src.simulation.detection_generator import Detection
from src.mapping.road_routing import get_osrm_route


# Colour palette for trajectory segments
_SEGMENT_COLOURS = {
    "observed": "#2ecc71",    # Green
    "inferred": "#f39c12",    # Orange
    "uncertain": "#e74c3c",   # Red
}

_CAMERA_ICON_COLOUR = "darkblue"


class MapVisualizer:
    """
    Build interactive Folium maps for the ANPR simulation.
    """

    def __init__(self, camera_graph: CameraGraph) -> None:
        self.graph = camera_graph
        self._center = self._compute_center()

    def _compute_center(self) -> Tuple[float, float]:
        """Compute the geographic centre of all cameras."""
        lats, lons = [], []
        for cam_id in self.graph.get_all_camera_ids():
            pos = self.graph.get_camera_position(cam_id)
            if pos:
                lats.append(pos[0])
                lons.append(pos[1])
        if lats:
            return (np.mean(lats), np.mean(lons))
        return (28.6400, 77.2280)  # Default fallback

    # ── Camera network map ──────────────────────────────────────────────

    def create_camera_network_map(
        self,
        zoom_start: int = 15,
        show_connections: bool = True,
    ) -> folium.Map:
        """
        Create a map showing all cameras and their directed connections.
        """
        m = folium.Map(
            location=self._center,
            zoom_start=zoom_start,
            tiles="OpenStreetMap",
        )

        # Camera markers
        for cam_id in self.graph.get_all_camera_ids():
            cam = self.graph.get_camera(cam_id)
            if cam is None:
                continue

            popup_html = (
                f"<b>{cam.camera_id}</b><br>"
                f"{cam.name}<br>"
                f"Entry: {', '.join(cam.entry_directions)}<br>"
                f"Exit: {', '.join(cam.exit_directions)}<br>"
                f"Connected to: {', '.join(cam.connected_cameras)}"
            )

            folium.Marker(
                location=[cam.latitude, cam.longitude],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"{cam.camera_id}: {cam.name}",
                icon=folium.Icon(
                    color=_CAMERA_ICON_COLOUR,
                    icon="video-camera",
                    prefix="fa",
                ),
            ).add_to(m)

        # Directed connections
        if show_connections:
            for src, dst, data in self.graph.get_all_edges():
                pos_src = self.graph.get_camera_position(src)
                pos_dst = self.graph.get_camera_position(dst)
                if pos_src and pos_dst:
                    mean_tt = data.get("mean_travel_time", 0)
                    tooltip = f"{src} → {dst}: ~{mean_tt:.0f}s"

                    # Draw line
                    folium.PolyLine(
                        locations=[list(pos_src), list(pos_dst)],
                        color="#3498db",
                        weight=2,
                        opacity=0.7,
                        tooltip=tooltip,
                        dash_array="5 10",
                    ).add_to(m)

                    # Arrow marker at midpoint
                    mid_lat = (pos_src[0] + pos_dst[0]) / 2
                    mid_lon = (pos_src[1] + pos_dst[1]) / 2

                    # Calculate bearing for arrow direction
                    bearing = self._calculate_bearing(
                        pos_src[0], pos_src[1], pos_dst[0], pos_dst[1]
                    )

                    folium.RegularPolygonMarker(
                        location=[mid_lat, mid_lon],
                        number_of_sides=3,
                        radius=6,
                        rotation=bearing - 90,
                        color="#3498db",
                        fill=True,
                        fill_color="#3498db",
                        fill_opacity=0.8,
                    ).add_to(m)

        return m

    # ── Trajectory map ──────────────────────────────────────────────────

    def create_trajectory_map(
        self,
        trajectory: ReconstructedTrajectory,
        det_map: Dict[str, Detection],
        zoom_start: int = 15,
        use_osrm: bool = False,
    ) -> folium.Map:
        """
        Create a map showing a single reconstructed trajectory overlaid
        on the camera network.
        """
        m = self.create_camera_network_map(zoom_start=zoom_start, show_connections=False)

        # Draw trajectory segments
        for seg in trajectory.segments:
            pos_from = self.graph.get_camera_position(seg.from_camera)
            pos_to = self.graph.get_camera_position(seg.to_camera)
            if pos_from is None or pos_to is None:
                continue

            colour = _SEGMENT_COLOURS.get(seg.segment_type, "#95a5a6")

            tooltip_text = (
                f"{seg.from_camera} → {seg.to_camera}<br>"
                f"Type: {seg.segment_type}<br>"
                f"Elapsed: {seg.elapsed_seconds:.0f}s<br>"
                f"Confidence: {seg.confidence:.2f}"
            )

            # Camera-to-camera movement is an inference, even when the graph
            # contains a direct edge between the observed camera locations.
            dash = "10 5" if seg.segment_type != "observed" else None

            route_geometry = get_osrm_route(pos_from, pos_to) if use_osrm else None
            display_geometry = (
                [list(pos_from), *route_geometry, list(pos_to)]
                if route_geometry else [list(pos_from), list(pos_to)]
            )
            folium.PolyLine(
                locations=display_geometry,
                color=colour,
                weight=4,
                opacity=0.9,
                tooltip=(
                    f"{tooltip_text}<br>OSRM suggested road geometry; "
                    "not a confirmed vehicle path."
                    if route_geometry else
                    f"{tooltip_text}<br>Straight-line fallback; not a confirmed path."
                ),
                dash_array=dash,
            ).add_to(m)

            # Direction arrow
            if route_geometry:
                middle = len(route_geometry) // 2
                arrow_from = route_geometry[max(0, middle - 1)]
                arrow_to = route_geometry[min(len(route_geometry) - 1, middle + 1)]
                mid_lat, mid_lon = route_geometry[middle]
            else:
                arrow_from, arrow_to = pos_from, pos_to
                mid_lat = (pos_from[0] + pos_to[0]) / 2
                mid_lon = (pos_from[1] + pos_to[1]) / 2
            bearing = self._calculate_bearing(
                arrow_from[0], arrow_from[1], arrow_to[0], arrow_to[1]
            )
            folium.RegularPolygonMarker(
                location=[mid_lat, mid_lon],
                number_of_sides=3,
                radius=8,
                rotation=bearing - 90,
                color=colour,
                fill=True,
                fill_color=colour,
                fill_opacity=0.9,
            ).add_to(m)

        # Mark detection points on the trajectory
        for det_id in trajectory.detection_ids:
            det = det_map.get(det_id)
            if det is None:
                continue
            pos = self.graph.get_camera_position(det.camera_id)
            if pos is None:
                continue

            popup_html = (
                f"<b>Detection: {det.detection_id}</b><br>"
                f"Camera: {det.camera_id}<br>"
                f"Plate: {det.recognised_plate}<br>"
                f"Confidence: {det.ocr_confidence:.2f}<br>"
                f"Type: {det.vehicle_type}<br>"
                f"Colour: {det.vehicle_colour}<br>"
                f"Direction: {det.travel_direction}"
            )

            folium.CircleMarker(
                location=[pos[0], pos[1]],
                radius=8,
                color="#e74c3c",
                fill=True,
                fill_color="#e74c3c",
                fill_opacity=0.8,
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"{det.recognised_plate} @ {det.camera_id}",
            ).add_to(m)

        # Add legend
        self._add_legend(m)

        return m

    @staticmethod
    def create_saved_trajectory_map(
        sightings: List[Dict],
        zoom_start: int = 14,
        use_osrm: bool = False,
    ) -> folium.Map:
        """Render persisted camera-coordinate sightings and inferred links."""
        if sightings:
            center = [
                float(np.mean([point["latitude"] for point in sightings])),
                float(np.mean([point["longitude"] for point in sightings])),
            ]
        else:
            center = [28.6400, 77.2280]
        map_view = folium.Map(location=center, zoom_start=zoom_start, tiles="OpenStreetMap")

        for index, point in enumerate(sightings):
            lat_lon = [point["latitude"], point["longitude"]]
            if index > 0:
                previous = sightings[index - 1]
                segment_type = point.get("segment_from_previous") or "uncertain"
                colour = _SEGMENT_COLOURS.get(segment_type, "#95a5a6")
                start = (previous["latitude"], previous["longitude"])
                end = (point["latitude"], point["longitude"])
                route_geometry = get_osrm_route(start, end) if use_osrm else None
                display_geometry = (
                    [list(start), *route_geometry, list(end)]
                    if route_geometry else [list(start), list(end)]
                )
                folium.PolyLine(
                    locations=display_geometry,
                    color=colour,
                    weight=4,
                    opacity=0.85,
                    dash_array="8 6",
                    tooltip=(
                        f"{previous['camera_id']} → {point['camera_id']} · "
                        f"{segment_type} · confidence "
                        f"{point.get('segment_confidence') or 0:.2f} · "
                        f"{'OSRM road estimate' if route_geometry else 'straight-line fallback'}; "
                        "not confirmed vehicle movement"
                    ),
                ).add_to(map_view)

            folium.CircleMarker(
                location=lat_lon,
                radius=8,
                color="#e74c3c",
                fill=True,
                fill_color="#e74c3c",
                fill_opacity=0.85,
                tooltip=f"{point['camera_id']} · {point['recognised_plate']}",
                popup=folium.Popup(
                    f"<b>{point['camera_id']}</b><br>"
                    f"Plate: {point['recognised_plate']}<br>"
                    f"Observed timestamp: {point['observed_at']:.1f}<br>"
                    f"OCR confidence: {point['ocr_confidence']:.2f}",
                    max_width=300,
                ),
            ).add_to(map_view)

        return map_view

    # ── Multi-trajectory map ────────────────────────────────────────────

    def create_multi_trajectory_map(
        self,
        trajectories: List[ReconstructedTrajectory],
        det_map: Dict[str, Detection],
        zoom_start: int = 14,
    ) -> folium.Map:
        """Create a map showing multiple trajectories with distinct colours."""
        m = self.create_camera_network_map(zoom_start=zoom_start)

        palette = [
            "#e74c3c", "#2ecc71", "#3498db", "#9b59b6",
            "#f39c12", "#1abc9c", "#e67e22", "#2c3e50",
        ]

        for idx, traj in enumerate(trajectories):
            colour = palette[idx % len(palette)]
            fg = folium.FeatureGroup(name=traj.trajectory_id)

            for seg in traj.segments:
                pos_from = self.graph.get_camera_position(seg.from_camera)
                pos_to = self.graph.get_camera_position(seg.to_camera)
                if pos_from and pos_to:
                    dash = "10 5" if seg.segment_type != "observed" else None
                    folium.PolyLine(
                        locations=[list(pos_from), list(pos_to)],
                        color=colour,
                        weight=3,
                        opacity=0.8,
                        dash_array=dash,
                        tooltip=f"{traj.trajectory_id}: {seg.from_camera}→{seg.to_camera}",
                    ).add_to(fg)

            fg.add_to(m)

        folium.LayerControl().add_to(m)
        return m

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate bearing between two geographic points (degrees)."""
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        dlon = lon2 - lon1
        x = np.sin(dlon) * np.cos(lat2)
        y = np.cos(lat1) * np.sin(lat2) - np.sin(lat1) * np.cos(lat2) * np.cos(dlon)
        bearing = np.degrees(np.arctan2(x, y))
        return (bearing + 360) % 360

    @staticmethod
    def _add_legend(m: folium.Map) -> None:
        """Add a legend to the map."""
        legend_html = """
        <div style="
            position: fixed;
            bottom: 50px; left: 50px;
            background: rgba(255,255,255,0.9);
            border: 2px solid #333;
            border-radius: 8px;
            padding: 10px 14px;
            font-size: 13px;
            z-index: 9999;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        ">
            <b>Trajectory Legend</b><br>
            <span style="color:#2ecc71;">━━</span> Observed segment<br>
            <span style="color:#f39c12;">┅ ┅</span> Inferred segment<br>
            <span style="color:#e74c3c;">┅ ┅</span> Uncertain segment<br>
            <span style="color:#3498db;">┅ ┅</span> Camera connection<br>
            <span style="color:darkblue;">📹</span> Camera
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))
