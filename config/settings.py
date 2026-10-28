"""
Configuration settings for the City-Wide ANPR Trajectory Engine Simulation.

All default parameters, scoring weights, and simulation controls are centralized here.
These can be overridden via the Streamlit dashboard UI.
"""

from dataclasses import dataclass, field
import math
from typing import Dict, List, Tuple
import numpy as np


def _finite_number(name: str, value: float) -> float:
    """Return a numeric value as float or raise a useful configuration error."""
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, float, np.integer, np.floating)
    ):
        raise ValueError(f"{name} must be a finite number.")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number.") from exc
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be a finite number.")
    return numeric


def _validate_unit_interval(name: str, value: float) -> None:
    numeric = _finite_number(name, value)
    if not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1 inclusive.")


@dataclass
class SimulationSettings:
    """Core simulation parameters."""
    num_vehicles: int = 100
    num_cameras: int = 8
    simulation_duration_hours: float = 4.0
    random_seed: int = 42
    
    # OCR / detection imperfections
    ocr_error_rate: float = 0.15          # Probability of character-level OCR error
    detection_failure_rate: float = 0.10  # Probability a camera misses a vehicle
    camera_detection_failure_rates: Dict[str, float] = field(default_factory=dict)
    reid_noise_level: float = 0.15        # Std-dev of Gaussian noise on Re-ID embeddings
    similar_appearance_rate: float = 0.10  # Chance a vehicle resembles an earlier vehicle
    unexpected_order_rate: float = 0.05   # Chance per vehicle of an out-of-order camera timestamp
    
    # Vehicle generation
    embedding_dim: int = 128              # Dimension of Re-ID appearance embeddings
    min_route_length: int = 2             # Minimum cameras a vehicle visits
    max_route_length: int = 6             # Maximum cameras a vehicle visits
    
    # Multi-frame observation
    multi_frame_enabled: bool = True
    max_observations_per_camera: int = 3  # Max frames per vehicle per camera

    def __post_init__(self) -> None:
        if isinstance(self.num_vehicles, bool) or not isinstance(self.num_vehicles, int) or self.num_vehicles < 1:
            raise ValueError("num_vehicles must be a positive integer.")
        if isinstance(self.num_cameras, bool) or not isinstance(self.num_cameras, int) or not 4 <= self.num_cameras <= 16:
            raise ValueError("num_cameras must be an integer from 4 to 16.")
        if isinstance(self.random_seed, bool) or not isinstance(self.random_seed, int) or self.random_seed < 0:
            raise ValueError("random_seed must be a non-negative integer.")
        if _finite_number("simulation_duration_hours", self.simulation_duration_hours) <= 0:
            raise ValueError("simulation_duration_hours must be greater than zero.")

        for name in (
            "ocr_error_rate", "detection_failure_rate", "reid_noise_level",
            "similar_appearance_rate", "unexpected_order_rate",
        ):
            _validate_unit_interval(name, getattr(self, name))
        for camera_id, rate in self.camera_detection_failure_rates.items():
            if not isinstance(camera_id, str) or not camera_id.strip():
                raise ValueError("Camera failure-rate overrides need non-empty camera IDs.")
            _validate_unit_interval(f"camera_detection_failure_rates[{camera_id}]", rate)

        if isinstance(self.embedding_dim, bool) or not isinstance(self.embedding_dim, int) or self.embedding_dim < 1:
            raise ValueError("embedding_dim must be a positive integer.")
        if isinstance(self.min_route_length, bool) or not isinstance(self.min_route_length, int) or self.min_route_length < 1:
            raise ValueError("min_route_length must be a positive integer.")
        if isinstance(self.max_route_length, bool) or not isinstance(self.max_route_length, int) or self.max_route_length < self.min_route_length:
            raise ValueError("max_route_length must be an integer at least as large as min_route_length.")
        if isinstance(self.max_observations_per_camera, bool) or not isinstance(self.max_observations_per_camera, int) or self.max_observations_per_camera < 1:
            raise ValueError("max_observations_per_camera must be a positive integer.")


@dataclass
class AssociationWeights:
    """Weights for the cross-camera association scoring function."""
    plate_similarity: float = 0.30
    reid_similarity: float = 0.25
    vehicle_type_match: float = 0.10
    colour_match: float = 0.10
    clm_plausibility: float = 0.15
    timestamp_score: float = 0.05
    direction_match: float = 0.05
    
    # Hard-constraint thresholds
    min_association_score: float = 0.45   # Minimum combined score to accept a match
    max_time_gap_seconds: float = 7200.0  # 2 hours max between sightings
    min_plate_similarity: float = 0.3     # Below this, reject outright

    def __post_init__(self) -> None:
        for name in (
            "plate_similarity", "reid_similarity", "vehicle_type_match",
            "colour_match", "clm_plausibility", "timestamp_score", "direction_match",
        ):
            if _finite_number(name, getattr(self, name)) < 0:
                raise ValueError(f"{name} weight cannot be negative.")
        for name in ("min_association_score", "min_plate_similarity"):
            _validate_unit_interval(name, getattr(self, name))
        if _finite_number("max_time_gap_seconds", self.max_time_gap_seconds) <= 0:
            raise ValueError("max_time_gap_seconds must be greater than zero.")
    

@dataclass
class CameraConfig:
    """Configuration for a single ANPR camera node."""
    camera_id: str
    name: str
    latitude: float
    longitude: float
    entry_directions: List[str] = field(default_factory=list)
    exit_directions: List[str] = field(default_factory=list)
    connected_cameras: List[str] = field(default_factory=list)
    travel_time_distributions: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    transition_probabilities: Dict[str, float] = field(default_factory=dict)
    # travel_time_distributions maps target_camera_id -> (mean_seconds, std_seconds)


# ── SmartCity default camera layout ─────────────────────────────────────────
# Coordinates are for a hypothetical city loosely modeled on a mid-size Indian city grid.
# These are illustrative; the map visualization will place markers here.

DEFAULT_CAMERAS: List[Dict] = [
    {
        "camera_id": "CAM-01",
        "name": "North Gate Entrance",
        "latitude": 28.6500,
        "longitude": 77.2300,
        "entry_directions": ["N", "NE"],
        "exit_directions": ["S", "SE"],
        "connected_cameras": ["CAM-02", "CAM-03"],
        "travel_time_distributions": {"CAM-02": (300, 60), "CAM-03": (420, 90)},
    },
    {
        "camera_id": "CAM-02",
        "name": "Central Market Junction",
        "latitude": 28.6450,
        "longitude": 77.2320,
        "entry_directions": ["N", "W"],
        "exit_directions": ["S", "E"],
        "connected_cameras": ["CAM-04", "CAM-05"],
        "travel_time_distributions": {"CAM-04": (240, 50), "CAM-05": (360, 80)},
    },
    {
        "camera_id": "CAM-03",
        "name": "University Road",
        "latitude": 28.6470,
        "longitude": 77.2250,
        "entry_directions": ["N", "NW"],
        "exit_directions": ["S", "SE"],
        "connected_cameras": ["CAM-04", "CAM-06"],
        "travel_time_distributions": {"CAM-04": (180, 40), "CAM-06": (300, 70)},
    },
    {
        "camera_id": "CAM-04",
        "name": "City Centre Roundabout",
        "latitude": 28.6420,
        "longitude": 77.2280,
        "entry_directions": ["N", "E", "W"],
        "exit_directions": ["S", "E", "W"],
        "connected_cameras": ["CAM-05", "CAM-06", "CAM-07"],
        "travel_time_distributions": {
            "CAM-05": (200, 45),
            "CAM-06": (150, 35),
            "CAM-07": (280, 60),
        },
    },
    {
        "camera_id": "CAM-05",
        "name": "Industrial Zone Gate",
        "latitude": 28.6400,
        "longitude": 77.2350,
        "entry_directions": ["N", "W"],
        "exit_directions": ["S", "E"],
        "connected_cameras": ["CAM-07", "CAM-08"],
        "travel_time_distributions": {"CAM-07": (320, 70), "CAM-08": (400, 85)},
    },
    {
        "camera_id": "CAM-06",
        "name": "Residential Block A",
        "latitude": 28.6410,
        "longitude": 77.2220,
        "entry_directions": ["N", "E"],
        "exit_directions": ["S", "W"],
        "connected_cameras": ["CAM-07", "CAM-08"],
        "travel_time_distributions": {"CAM-07": (250, 55), "CAM-08": (350, 75)},
    },
    {
        "camera_id": "CAM-07",
        "name": "South Highway Interchange",
        "latitude": 28.6370,
        "longitude": 77.2290,
        "entry_directions": ["N", "NE", "NW"],
        "exit_directions": ["S"],
        "connected_cameras": ["CAM-08"],
        "travel_time_distributions": {"CAM-08": (200, 40)},
    },
    {
        "camera_id": "CAM-08",
        "name": "South Exit Toll Plaza",
        "latitude": 28.6340,
        "longitude": 77.2310,
        "entry_directions": ["N", "NW"],
        "exit_directions": ["S", "SE"],
        "connected_cameras": [],
        "travel_time_distributions": {},
    },
]


# ── Vehicle types and colours ────────────────────────────────────────────────

VEHICLE_TYPES: List[str] = [
    "Sedan", "SUV", "Hatchback", "Truck", "Bus",
    "Motorcycle", "Van", "Auto-Rickshaw",
]

VEHICLE_COLOURS: List[str] = [
    "White", "Black", "Silver", "Red", "Blue",
    "Grey", "Green", "Yellow", "Brown", "Orange",
]

# Indian-style plate prefixes for realism
PLATE_PREFIXES: List[str] = [
    "DL", "MH", "KA", "TN", "UP", "RJ", "GJ", "HR",
]


# ── Evaluation ───────────────────────────────────────────────────────────────

@dataclass
class EvaluationConfig:
    """Settings for evaluation metrics."""
    compare_methods: List[str] = field(
        default_factory=lambda: ["plate_only", "reid_only", "combined"]
    )
