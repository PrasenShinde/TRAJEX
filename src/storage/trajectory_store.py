"""SQLite persistence and lookup for synthetic trajectory runs."""

from dataclasses import asdict
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Dict, List, Optional
from uuid import uuid4

from config.settings import SimulationSettings
from src.camera_network.camera_graph import CameraGraph
from src.simulation.detection_generator import Detection
from src.trajectory.trajectory_reconstruction import ReconstructedTrajectory


class TrajectoryStore:
    """Store detections and reconstructed camera-coordinate trajectories."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS simulation_runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    settings_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS run_cameras (
                    run_id TEXT NOT NULL,
                    camera_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    PRIMARY KEY (run_id, camera_id),
                    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS detection_events (
                    run_id TEXT NOT NULL,
                    detection_id TEXT NOT NULL,
                    camera_id TEXT NOT NULL,
                    observed_at REAL NOT NULL,
                    recognised_plate TEXT NOT NULL,
                    ocr_confidence REAL NOT NULL,
                    vehicle_type TEXT NOT NULL,
                    vehicle_colour TEXT NOT NULL,
                    travel_direction TEXT NOT NULL,
                    detection_confidence REAL NOT NULL,
                    PRIMARY KEY (run_id, detection_id),
                    FOREIGN KEY (run_id, camera_id) REFERENCES run_cameras(run_id, camera_id)
                );
                CREATE INDEX IF NOT EXISTS idx_detections_run_plate
                    ON detection_events(run_id, recognised_plate);
                CREATE TABLE IF NOT EXISTS evaluation_ground_truth (
                    run_id TEXT NOT NULL,
                    detection_id TEXT NOT NULL,
                    ground_truth_vehicle_id TEXT NOT NULL,
                    route_sequence_index INTEGER NOT NULL DEFAULT 0,
                    timestamp_order_anomaly INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (run_id, detection_id),
                    FOREIGN KEY (run_id, detection_id)
                        REFERENCES detection_events(run_id, detection_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS reconstructed_trajectories (
                    run_id TEXT NOT NULL,
                    trajectory_id TEXT NOT NULL,
                    overall_confidence REAL NOT NULL,
                    num_detections INTEGER NOT NULL,
                    PRIMARY KEY (run_id, trajectory_id),
                    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS trajectory_sightings (
                    run_id TEXT NOT NULL,
                    trajectory_id TEXT NOT NULL,
                    sequence_index INTEGER NOT NULL,
                    detection_id TEXT NOT NULL,
                    camera_id TEXT NOT NULL,
                    observed_at REAL NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    recognised_plate TEXT NOT NULL,
                    ocr_confidence REAL NOT NULL,
                    segment_from_previous TEXT,
                    segment_confidence REAL,
                    segment_explanation TEXT,
                    PRIMARY KEY (run_id, trajectory_id, sequence_index),
                    FOREIGN KEY (run_id, trajectory_id)
                        REFERENCES reconstructed_trajectories(run_id, trajectory_id) ON DELETE CASCADE,
                    FOREIGN KEY (run_id, detection_id)
                        REFERENCES detection_events(run_id, detection_id)
                );
                CREATE INDEX IF NOT EXISTS idx_sightings_run_plate
                    ON trajectory_sightings(run_id, recognised_plate);
            """)
            truth_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(evaluation_ground_truth)")
            }
            if "route_sequence_index" not in truth_columns:
                connection.execute(
                    "ALTER TABLE evaluation_ground_truth "
                    "ADD COLUMN route_sequence_index INTEGER NOT NULL DEFAULT 0"
                )
            if "timestamp_order_anomaly" not in truth_columns:
                connection.execute(
                    "ALTER TABLE evaluation_ground_truth "
                    "ADD COLUMN timestamp_order_anomaly INTEGER NOT NULL DEFAULT 0"
                )

    def save_run(
        self,
        settings: SimulationSettings,
        detections: List[Detection],
        trajectories: List[ReconstructedTrajectory],
        camera_graph: CameraGraph,
    ) -> str:
        """Persist one completed simulation and return its unique run ID."""
        run_id = f"RUN-{datetime.now(timezone.utc):%Y%m%dT%H%M%S.%fZ}-{uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()

        with self._connection() as connection:
            connection.execute(
                "INSERT INTO simulation_runs VALUES (?, ?, ?)",
                (run_id, created_at, json.dumps(asdict(settings), sort_keys=True)),
            )
            connection.executemany(
                "INSERT INTO run_cameras VALUES (?, ?, ?, ?, ?)",
                [
                    (run_id, camera.camera_id, camera.name, camera.latitude, camera.longitude)
                    for camera in camera_graph.get_all_cameras().values()
                ],
            )
            connection.executemany(
                "INSERT INTO detection_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        run_id, detection.detection_id, detection.camera_id,
                        detection.timestamp, detection.recognised_plate,
                        detection.ocr_confidence, detection.vehicle_type,
                        detection.vehicle_colour, detection.travel_direction,
                        detection.detection_confidence,
                    )
                    for detection in detections
                ],
            )
            # Keep evaluation-only identity labels in a separate table so the
            # reconstructed tracking records cannot accidentally use them.
            connection.executemany(
                "INSERT INTO evaluation_ground_truth "
                "(run_id, detection_id, ground_truth_vehicle_id, route_sequence_index, "
                "timestamp_order_anomaly) VALUES (?, ?, ?, ?, ?)",
                [
                    (run_id, d.detection_id, d.ground_truth_vehicle_id,
                     d.ground_truth_route_index, int(d.is_timestamp_order_anomaly))
                    for d in detections
                ],
            )

            trajectory_rows = []
            sighting_rows = []
            det_map = {d.detection_id: d for d in detections}
            cameras = camera_graph.get_all_cameras()
            for trajectory in trajectories:
                trajectory_rows.append((
                    run_id, trajectory.trajectory_id,
                    trajectory.overall_confidence, len(trajectory.detection_ids),
                ))
                for index, detection_id in enumerate(trajectory.detection_ids):
                    detection = det_map.get(detection_id)
                    if detection is None:
                        continue
                    camera = cameras.get(detection.camera_id)
                    if camera is None:
                        continue
                    segment = trajectory.segments[index - 1] if index > 0 else None
                    sighting_rows.append((
                        run_id, trajectory.trajectory_id, index, detection_id,
                        detection.camera_id, detection.timestamp,
                        camera.latitude, camera.longitude,
                        detection.recognised_plate, detection.ocr_confidence,
                        segment.segment_type if segment else None,
                        segment.confidence if segment else None,
                        segment.explanation if segment else None,
                    ))
            connection.executemany(
                "INSERT INTO reconstructed_trajectories VALUES (?, ?, ?, ?)",
                trajectory_rows,
            )
            connection.executemany(
                "INSERT INTO trajectory_sightings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                sighting_rows,
            )
        return run_id

    def list_runs(self, limit: int = 20) -> List[Dict]:
        with self._connection() as connection:
            rows = connection.execute("""
                SELECT r.run_id, r.created_at, r.settings_json,
                       (SELECT COUNT(*) FROM reconstructed_trajectories t
                        WHERE t.run_id = r.run_id) AS trajectory_count,
                       (SELECT COUNT(*) FROM detection_events d
                        WHERE d.run_id = r.run_id) AS detection_count,
                       (SELECT COUNT(*) FROM run_cameras c
                        WHERE c.run_id = r.run_id) AS camera_count
                FROM simulation_runs r
                ORDER BY r.created_at DESC LIMIT ?
            """, (limit,)).fetchall()
        runs = []
        for row in rows:
            run = dict(row)
            try:
                settings = json.loads(run.pop("settings_json"))
            except (TypeError, json.JSONDecodeError):
                settings = {}
            run["vehicle_count"] = settings.get("num_vehicles")
            runs.append(run)
        return runs

    def search_trajectories(self, run_id: str, query: str = "", limit: int = 100) -> List[Dict]:
        """Search one run by reconstructed ID or any recognized plate sighting."""
        pattern = f"%{query.strip()}%"
        with self._connection() as connection:
            rows = connection.execute("""
                SELECT t.trajectory_id, t.overall_confidence, t.num_detections,
                       GROUP_CONCAT(DISTINCT s.recognised_plate) AS plates,
                       MIN(s.observed_at) AS first_seen, MAX(s.observed_at) AS last_seen
                FROM reconstructed_trajectories t
                LEFT JOIN trajectory_sightings s
                    ON s.run_id = t.run_id AND s.trajectory_id = t.trajectory_id
                WHERE t.run_id = ? AND (
                    t.trajectory_id LIKE ? OR EXISTS (
                        SELECT 1 FROM trajectory_sightings match_sighting
                        WHERE match_sighting.run_id = t.run_id
                          AND match_sighting.trajectory_id = t.trajectory_id
                          AND match_sighting.recognised_plate LIKE ?
                    )
                )
                GROUP BY t.run_id, t.trajectory_id
                ORDER BY t.num_detections DESC, t.trajectory_id
                LIMIT ?
            """, (run_id, pattern, pattern, limit)).fetchall()
        return [dict(row) for row in rows]

    def search_detection_events(
        self, run_id: str, query: str, limit: int = 200
    ) -> List[Dict]:
        """Search all saved OCR sightings, including detections outside tracking samples.

        These rows are raw observed camera events, not reconstructed identities.
        Ground-truth identity fields are intentionally never returned.
        """
        if not query or not query.strip():
            return []
        pattern = f"%{query.strip()}%"
        with self._connection() as connection:
            rows = connection.execute("""
                SELECT d.detection_id, d.camera_id, c.name AS camera_name,
                       d.observed_at, d.recognised_plate, d.ocr_confidence,
                       d.vehicle_type, d.vehicle_colour, c.latitude, c.longitude,
                       EXISTS (
                           SELECT 1 FROM trajectory_sightings s
                           WHERE s.run_id = d.run_id AND s.detection_id = d.detection_id
                       ) AS included_in_reconstruction
                FROM detection_events d
                JOIN run_cameras c
                  ON c.run_id = d.run_id AND c.camera_id = d.camera_id
                WHERE d.run_id = ? AND d.recognised_plate LIKE ?
                ORDER BY d.observed_at, d.detection_id
                LIMIT ?
            """, (run_id, pattern, limit)).fetchall()
        return [dict(row) for row in rows]

    def get_trajectory(self, run_id: str, trajectory_id: str) -> Optional[Dict]:
        with self._connection() as connection:
            trajectory = connection.execute(
                "SELECT * FROM reconstructed_trajectories WHERE run_id = ? AND trajectory_id = ?",
                (run_id, trajectory_id),
            ).fetchone()
            if trajectory is None:
                return None
            sightings = connection.execute("""
                SELECT * FROM trajectory_sightings
                WHERE run_id = ? AND trajectory_id = ?
                ORDER BY sequence_index
            """, (run_id, trajectory_id)).fetchall()
        return {"trajectory": dict(trajectory), "sightings": [dict(row) for row in sightings]}
