"""
City-Wide ANPR Trajectory Engine Simulation — Streamlit Dashboard.

This is the main entry point for the interactive simulation.
Run with: streamlit run app.py

DISCLAIMER: This application uses entirely SYNTHETIC data and simulated
AI modules.  No actual OCR, vehicle detection, or Re-ID inference is
performed.  All outputs are illustrative of how a production system
would operate, not real surveillance results.
"""

import sys
import os
import time
import io
import zipfile
from datetime import datetime, timedelta
from collections import Counter
from pathlib import Path

import streamlit as st
import pandas as pd
import numpy as np

# Ensure project root is on PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import (
    SimulationSettings,
    AssociationWeights,
    DEFAULT_CAMERAS,
)
from src.simulation.city_generator import CityGenerator
from src.simulation.vehicle_generator import VehicleGenerator, Vehicle
from src.simulation.detection_generator import DetectionGenerator, Detection
from src.camera_network.camera_graph import CameraGraph
from src.camera_network.camera_link_model import CameraLinkModel
from src.association.similarity import SimilarityScorer
from src.association.association_engine import AssociationEngine, AssociationRecord
from src.trajectory.trajectory_reconstruction import (
    TrajectoryReconstructor,
    ReconstructedTrajectory,
)
from src.evaluation.metrics import EvaluationEngine, EvaluationResult
from src.evaluation.sensitivity import run_sensitivity_analysis
from src.mapping.map_visualization import MapVisualizer
from src.utils.scenario_export import export_scenario
from src.storage.trajectory_store import TrajectoryStore

# ── Page configuration ──────────────────────────────────────────────────
st.set_page_config(
    page_title="SmartCity ANPR Trajectory Engine",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .main-header {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        color: white;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }

    .main-header h1 {
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
        background: linear-gradient(90deg, #667eea, #764ba2, #f093fb);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .main-header p {
        color: #b0b3c5;
        margin: 0.5rem 0 0 0;
        font-size: 0.95rem;
    }

    .metric-card {
        background: linear-gradient(145deg, #1a1a2e, #16213e);
        border: 1px solid rgba(102, 126, 234, 0.2);
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.3);
    }

    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #667eea;
    }

    .metric-label {
        font-size: 0.8rem;
        color: #8892b0;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 0.3rem;
    }

    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
    }

    .badge-accepted {
        background: rgba(46, 204, 113, 0.15);
        color: #2ecc71;
        border: 1px solid rgba(46, 204, 113, 0.3);
    }

    .badge-rejected {
        background: rgba(231, 76, 60, 0.15);
        color: #e74c3c;
        border: 1px solid rgba(231, 76, 60, 0.3);
    }

    .badge-uncertain {
        background: rgba(243, 156, 18, 0.15);
        color: #f39c12;
        border: 1px solid rgba(243, 156, 18, 0.3);
    }

    .section-header {
        font-size: 1.3rem;
        font-weight: 600;
        color: #ccd6f6;
        border-bottom: 2px solid rgba(102, 126, 234, 0.3);
        padding-bottom: 0.5rem;
        margin: 1.5rem 0 1rem 0;
    }

    .info-box {
        background: rgba(102, 126, 234, 0.08);
        border-left: 3px solid #667eea;
        padding: 0.8rem 1rem;
        border-radius: 0 8px 8px 0;
        margin: 0.8rem 0;
        font-size: 0.9rem;
    }

    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f0c29 0%, #1a1a2e 100%);
    }

    div[data-testid="stSidebar"] .stMarkdown h1,
    div[data-testid="stSidebar"] .stMarkdown h2,
    div[data-testid="stSidebar"] .stMarkdown h3 {
        color: #ccd6f6;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 8px 20px;
        font-weight: 500;
    }

    .disclaimer-box {
        background: rgba(231, 76, 60, 0.08);
        border: 1px solid rgba(231, 76, 60, 0.2);
        border-radius: 8px;
        padding: 0.7rem 1rem;
        font-size: 0.8rem;
        color: #e74c3c;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
#  SESSION STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════

def init_session_state():
    """Initialise session state with defaults."""
    defaults = {
        "simulation_run": False,
        "vehicles": None,
        "detections": None,
        "detections_df": None,
        "det_map": None,
        "camera_graph": None,
        "association_records": None,
        "clusters": None,
        "trajectories": None,
        "eval_results": None,
        "processing_time": 0.0,
        "processing_stage_times": {},
        "export_dir": None,
        "evaluation_detection_count": 0,
        "tracking_detection_count": 0,
        "sensitivity_results": None,
        "database_run_id": None,
        "settings": SimulationSettings(),
        "weights": AssociationWeights(),
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session_state()

trajectory_store = TrajectoryStore(
    Path(__file__).parent / "data" / "smartcity_trajectories.sqlite3"
)


def render_saved_trajectory_lookup(run_records, key_prefix: str) -> None:
    """Search persisted trajectories by reconstructed ID or recognized plate."""
    if not run_records:
        st.info("No saved runs yet. Run a simulation to save trajectories here.")
        return

    run_ids = [record["run_id"] for record in run_records]
    st.caption("Run history shows the 20 most recent saved runs.")
    selected_run = st.selectbox(
        "Saved simulation run",
        run_ids,
        format_func=lambda run_id: next(
            f"{run_id} · {record['vehicle_count'] or '?'} vehicles · "
            f"{record['detection_count']:,} detections · {record['camera_count']} cameras · "
            f"{record['trajectory_count']} trajectories · {record['created_at'][:19]} UTC"
            for record in run_records if record["run_id"] == run_id
        ),
        key=f"{key_prefix}_run",
    )
    query = st.text_input(
        "Search recognized plate or trajectory ID",
        placeholder="For example, DL05AB1234 or TRAJ-DET-0000012",
        key=f"{key_prefix}_query",
    )
    matches = trajectory_store.search_trajectories(selected_run, query)
    raw_events = trajectory_store.search_detection_events(selected_run, query)
    if len(matches) == 100:
        st.warning("Showing up to 100 reconstructed trajectories. Refine the search text to narrow the results.")
    if len(raw_events) == 200:
        st.warning("Showing up to 200 raw detection matches. Refine the search text to narrow the results.")
    if not matches:
        st.info("No reconstructed trajectory matched. Checking every saved camera detection for this OCR text.")
        if raw_events:
            st.caption(
                "These are raw observed detections, not linked vehicle identity or a reconstructed trajectory. "
                "OCR text can be wrong or shared by different vehicles."
            )
            raw_df = pd.DataFrame(raw_events).rename(columns={
                "detection_id": "Detection ID",
                "camera_id": "Camera ID",
                "camera_name": "Camera",
                "observed_at": "Simulation time (s)",
                "recognised_plate": "Recognized OCR text",
                "ocr_confidence": "OCR confidence",
                "vehicle_type": "Vehicle type",
                "vehicle_colour": "Vehicle colour",
                "latitude": "Latitude",
                "longitude": "Longitude",
                "included_in_reconstruction": "In reconstructed sample",
            })
            st.dataframe(raw_df, use_container_width=True, hide_index=True)
        elif query.strip():
            st.info("No saved camera detection contains that OCR text.")
        return

    selection = st.selectbox(
        "Matching reconstructed trajectories",
        range(len(matches)),
        format_func=lambda index: (
            f"{matches[index]['trajectory_id']} · {matches[index]['plates'] or 'plate unavailable'} · "
            f"{matches[index]['num_detections']} sightings"
        ),
        key=f"{key_prefix}_trajectory",
    )
    selected = matches[selection]
    saved = trajectory_store.get_trajectory(selected_run, selected["trajectory_id"])
    if not saved:
        st.warning("The selected trajectory is no longer available in this saved run.")
        return

    points = saved["sightings"]
    if raw_events:
        with st.expander("All raw detections containing this OCR text"):
            st.caption(
                "Raw camera events are not identity links. OCR text may be erroneous or shared; "
                "only detections marked as included belong to this reconstruction sample."
            )
            raw_df = pd.DataFrame(raw_events).rename(columns={
                "detection_id": "Detection ID",
                "camera_id": "Camera ID",
                "camera_name": "Camera",
                "observed_at": "Simulation time (s)",
                "recognised_plate": "Recognized OCR text",
                "ocr_confidence": "OCR confidence",
                "vehicle_type": "Vehicle type",
                "vehicle_colour": "Vehicle colour",
                "latitude": "Latitude",
                "longitude": "Longitude",
                "included_in_reconstruction": "In reconstructed sample",
            })
            st.dataframe(raw_df, use_container_width=True, hide_index=True)
    st.caption(
        f"Trajectory confidence {saved['trajectory']['overall_confidence']:.2f} · "
        "markers are observed camera locations; connecting roads are inferred."
    )
    point_table = pd.DataFrame([
        {
            "Step": point["sequence_index"] + 1,
            "Camera": point["camera_id"],
            "Observed time (simulation seconds)": round(point["observed_at"], 1),
            "Recognized plate": point["recognised_plate"],
            "OCR confidence": round(point["ocr_confidence"], 3),
            "Link from previous": point["segment_from_previous"] or "Start",
            "Link confidence": point["segment_confidence"],
            "Latitude": point["latitude"],
            "Longitude": point["longitude"],
        }
        for point in points
    ])
    st.dataframe(point_table, use_container_width=True, hide_index=True)
    use_osrm = st.checkbox(
        "Try OSM road routing (public OSRM service)",
        value=False,
        help="Sends the hypothetical camera coordinates to OSRM. If it cannot route them, the map draws a labelled straight-line fallback.",
        key=f"{key_prefix}_osrm",
    )
    try:
        from streamlit_folium import st_folium
        saved_map = MapVisualizer.create_saved_trajectory_map(points, use_osrm=use_osrm)
        st_folium(saved_map, width=None, height=500, key=f"{key_prefix}_map")
    except Exception as exc:
        st.warning(f"Saved trajectory map unavailable: {exc}")


# ═══════════════════════════════════════════════════════════════════════
#  SIMULATION ENGINE
# ═══════════════════════════════════════════════════════════════════════

def run_simulation(settings: SimulationSettings, weights: AssociationWeights):
    """Execute the full end-to-end simulation pipeline."""
    start_time = time.time()
    stage_times = {}
    stage_start = start_time
    progress = st.progress(0, text="Building camera network...")

    # 1. Build camera graph
    st.session_state.settings = settings
    st.session_state.weights = weights
    city = CityGenerator(settings)
    camera_graph = city.build()
    stage_times["Camera network"] = time.time() - stage_start
    stage_start = time.time()
    st.session_state.camera_graph = camera_graph
    progress.progress(10, text="Generating vehicles...")

    # 2. Generate vehicles
    vgen = VehicleGenerator(camera_graph, settings)
    vehicles = vgen.generate_vehicles()
    stage_times["Vehicle generation"] = time.time() - stage_start
    stage_start = time.time()
    st.session_state.vehicles = vehicles
    progress.progress(25, text="Generating detections...")

    # 3. Generate detections
    dgen = DetectionGenerator(camera_graph, settings)
    detections, det_df = dgen.generate_detections(vehicles)
    stage_times["Detection generation"] = time.time() - stage_start
    st.session_state.detections = detections
    st.session_state.detections_df = det_df
    det_map = {d.detection_id: d for d in detections}
    st.session_state.det_map = det_map
    progress.progress(40, text="Running cross-camera association...")
    stage_start = time.time()

    # 4. Association (all three methods)
    engine = AssociationEngine(camera_graph, weights)

    # For large datasets, limit pairwise comparisons for speed
    max_dets_for_full = 500
    if len(detections) > max_dets_for_full:
        # Sample the full timeline evenly to reduce temporal bias while keeping
        # the pairwise comparison workload bounded.
        eval_detections = sorted(detections, key=lambda d: d.timestamp)
        sample_indices = np.linspace(
            0, len(eval_detections) - 1, max_dets_for_full, dtype=int
        )
        windowed_detections = [eval_detections[i] for i in sample_indices]
    else:
        windowed_detections = detections
    st.session_state.evaluation_detection_count = len(windowed_detections)

    records_combined, clusters_combined = engine.associate(windowed_detections, method="combined")
    stage_times["Combined association"] = time.time() - stage_start
    stage_start = time.time()
    progress.progress(60, text="Running plate-only matching...")

    records_plate, clusters_plate = engine.associate(windowed_detections, method="plate_only")
    stage_times["Plate-only association"] = time.time() - stage_start
    stage_start = time.time()
    progress.progress(70, text="Running Re-ID-only matching...")

    records_reid, clusters_reid = engine.associate(windowed_detections, method="reid_only")
    stage_times["Re-ID-only association"] = time.time() - stage_start
    stage_start = time.time()
    progress.progress(80, text="Reconstructing trajectories...")

    st.session_state.association_records = {
        "combined": records_combined,
        "plate_only": records_plate,
        "reid_only": records_reid,
    }
    st.session_state.clusters = {
        "combined": clusters_combined,
        "plate_only": clusters_plate,
        "reid_only": clusters_reid,
    }

    # 5. Reconstruct the complete run for persistent search. Evaluation remains
    # on the same bounded sample for all three comparison methods.
    reconstructor = TrajectoryReconstructor(camera_graph)
    if len(windowed_detections) == len(detections):
        trajectories = reconstructor.reconstruct(clusters_combined, det_map)
    else:
        progress.progress(82, text=f"Tracking all {len(detections):,} detections...")
        tracking_records, tracking_clusters = engine.associate(
            detections, method="combined", record_all_candidates=False
        )
        del tracking_records
        trajectories = reconstructor.reconstruct(tracking_clusters, det_map)
    stage_times["Full-run trajectory tracking"] = time.time() - stage_start
    stage_start = time.time()
    st.session_state.tracking_detection_count = len(detections)
    st.session_state.trajectories = trajectories
    st.session_state.database_run_id = trajectory_store.save_run(
        settings, detections, trajectories, camera_graph
    )
    stage_times["SQLite persistence"] = time.time() - stage_start
    stage_start = time.time()
    progress.progress(90, text="Evaluating results...")

    # 6. Evaluation
    evaluator = EvaluationEngine()
    eval_results = {}
    trajectories_by_method = {}
    for method_name, records in st.session_state.association_records.items():
        clusters = st.session_state.clusters[method_name]
        method_trajs = reconstructor.reconstruct(clusters, det_map)
        trajectories_by_method[method_name] = method_trajs
        assoc_eval = evaluator.evaluate_associations(
            records, windowed_detections, method=method_name
        )
        traj_eval = evaluator.evaluate_trajectories(
            method_trajs, windowed_detections, method=method_name
        )
        # Merge trajectory-level metrics into the result
        assoc_eval.total_reconstructed_trajectories = traj_eval.total_reconstructed_trajectories
        # The dashboard's headline metrics describe reconstructed consecutive
        # transitions. Use that same basis for every displayed metric.
        assoc_eval.precision = traj_eval.precision
        assoc_eval.recall = traj_eval.recall
        assoc_eval.f1_score = traj_eval.f1_score
        assoc_eval.false_match_rate = traj_eval.false_match_rate
        assoc_eval.missed_association_rate = traj_eval.missed_association_rate
        assoc_eval.correct_associations = traj_eval.correct_associations
        assoc_eval.incorrect_associations = traj_eval.incorrect_associations
        assoc_eval.missed_associations = traj_eval.missed_associations
        assoc_eval.unmatched_detections = traj_eval.unmatched_detections
        assoc_eval.trajectory_completeness = traj_eval.trajectory_completeness
        assoc_eval.correct_transitions_pct = traj_eval.correct_transitions_pct
        assoc_eval.per_vehicle_details = traj_eval.per_vehicle_details
        eval_results[method_name] = assoc_eval

    st.session_state.eval_results = eval_results
    stage_times["Evaluation"] = time.time() - stage_start

    # Persist all generated scenario artifacts for later inspection and reuse.
    trajectories_by_method["combined"] = trajectories
    stage_start = time.time()
    st.session_state.export_dir = str(export_scenario(
        Path(__file__).parent / "data" / "generated",
        settings,
        vehicles,
        detections,
        det_df,
        st.session_state.association_records,
        trajectories_by_method,
        eval_results,
        len(windowed_detections),
        tracking_detection_count=len(detections),
    ))
    stage_times["Scenario export"] = time.time() - stage_start

    elapsed = time.time() - start_time
    st.session_state.processing_stage_times = stage_times
    st.session_state.processing_time = elapsed
    st.session_state.simulation_run = True

    progress.progress(100, text=f"Complete! ({elapsed:.1f}s)")
    time.sleep(0.5)
    progress.empty()


# ═══════════════════════════════════════════════════════════════════════
#  SIDEBAR — SIMULATION CONTROLS
# ═══════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## 🎛️ Simulation Controls")

    st.markdown('<div class="disclaimer-box">⚠️ All data is synthetic. '
                'No real surveillance is performed.</div>', unsafe_allow_html=True)

    with st.expander("What the controls mean"):
        st.markdown(
            """
            - **Vehicles / duration / cameras:** size and time span of the synthetic city run.
            - **Random seed:** same seed and settings reproduce the same generated scenario.
            - **OCR error:** chance a plate character is read incorrectly.
            - **Detection failure:** chance a camera misses a planned sighting; a per-camera override replaces the global rate for that camera.
            - **Re-ID noise:** changes the simulated appearance vector between sightings; higher values make it less consistent.
            - **Similar-looking vehicles:** chance two different synthetic cars receive similar appearance vectors.
            - **Unexpected camera order:** injects timestamp anomalies for evaluation; the matcher does not receive the ground-truth route order.
            - **Fuse multiple frames / maximum frames:** combine up to this many simulated plate frames at one camera into one sighting.
            - **Association weights:** relative influence of plate, appearance, vehicle type, colour, camera-link plausibility, elapsed time, and direction. Active weights are normalized automatically.
            - **Minimum association score:** minimum combined score required before a proposed link is accepted; a higher threshold leaves more sightings unlinked.

            These controls affect a synthetic simulation, not a real camera feed.
            """
        )

    st.markdown("### Vehicle & Duration")
    num_vehicles = st.slider("Number of vehicles", 10, 500, 100, 10,
                              help="Total synthetic vehicles in the simulation")
    num_cameras = st.slider(
        "Number of cameras", 4, 16, 8, 1,
        help="Build a connected subset or extended southbound corridor layout.",
    )
    sim_duration = st.slider(
        "Duration (hours)", 1.0, 12.0, 4.0, 0.5,
        help="Length of the synthetic observation window. Vehicles are assigned times within this window.",
    )
    random_seed = st.number_input(
        "Random seed", 0, 99999, 42,
        help="Use the same seed and settings to regenerate the same synthetic scenario.",
    )

    st.markdown("### Imperfections")
    ocr_error_rate = st.slider("OCR error rate", 0.0, 0.5, 0.15, 0.01,
                                help="Probability of per-character OCR error")
    det_failure_rate = st.slider("Detection failure rate", 0.0, 0.5, 0.10, 0.01,
                                  help="Probability a camera misses a vehicle")
    camera_failure_rates = {}
    with st.expander("Per-camera failure rate overrides"):
        st.caption("Enable an override for cameras that should use a different rate.")
        for camera_index in range(num_cameras):
            camera_id = f"CAM-{camera_index + 1:02d}"
            override_enabled = st.checkbox(
                f"Set a custom miss rate for {camera_id}",
                key=f"camera_failure_override_enabled_{camera_id}",
            )
            if override_enabled:
                camera_failure_rates[camera_id] = st.slider(
                    f"{camera_id} miss rate",
                    0.0, 0.5, float(det_failure_rate), 0.01,
                    key=f"camera_failure_rate_{camera_id}",
                )
    reid_noise = st.slider("Re-ID noise level", 0.0, 0.5, 0.15, 0.01,
                            help="Gaussian noise on appearance embeddings")
    similar_appearance_rate = st.slider(
        "Similar-looking vehicle rate", 0.0, 0.5, 0.10, 0.01,
        help="Chance a new synthetic vehicle gets an appearance vector near an earlier vehicle's vector.",
    )
    unexpected_order_rate = st.slider(
        "Unexpected camera-order rate", 0.0, 0.30, 0.05, 0.01,
        help="Chance per vehicle that one camera timestamp appears before the preceding route observation.",
    )
    multi_frame_enabled = st.checkbox(
        "Fuse multiple frames per camera", value=True,
        help="Combine simulated plate observations from several frames at one camera.",
    )
    max_observations_per_camera = st.slider(
        "Maximum frames per camera", 1, 5, 3, 1,
        disabled=not multi_frame_enabled,
    )

    st.markdown("### Association Weights")
    st.caption("Active weights are normalized to sum to 1 before scoring.")
    w_plate = st.slider("Plate weight", 0.0, 1.0, 0.30, 0.05, help="Importance of recognized plate similarity and OCR confidence.")
    w_reid = st.slider("Re-ID weight", 0.0, 1.0, 0.25, 0.05, help="Importance of similarity between synthetic appearance vectors.")
    w_type = st.slider("Type match weight", 0.0, 1.0, 0.10, 0.05, help="Importance of matching simulated vehicle types.")
    w_colour = st.slider("Colour match weight", 0.0, 1.0, 0.10, 0.05, help="Importance of matching simulated vehicle colours.")
    w_clm = st.slider("CLM weight", 0.0, 1.0, 0.15, 0.05, help="Importance of camera-graph connectivity and expected travel time.")
    w_time = st.slider("Timestamp weight", 0.0, 1.0, 0.05, 0.05, help="Importance of the elapsed time between sightings.")
    w_dir = st.slider("Direction weight", 0.0, 1.0, 0.05, 0.05, help="Importance of consistency between simulated travel directions.")
    min_score = st.slider("Min association score", 0.1, 0.9, 0.45, 0.05, help="Higher values accept fewer links and can leave more sightings unassigned.")

    st.markdown("---")

    col_run, col_reset = st.columns(2)
    with col_run:
        run_clicked = st.button("🚀 Run Simulation", type="primary", use_container_width=True)
    with col_reset:
        reset_clicked = st.button("🔄 Reset", use_container_width=True)

    if run_clicked:
        settings = SimulationSettings(
            num_vehicles=num_vehicles,
            num_cameras=num_cameras,
            simulation_duration_hours=sim_duration,
            random_seed=random_seed,
            ocr_error_rate=ocr_error_rate,
            detection_failure_rate=det_failure_rate,
            camera_detection_failure_rates=camera_failure_rates,
            reid_noise_level=reid_noise,
            similar_appearance_rate=similar_appearance_rate,
            unexpected_order_rate=unexpected_order_rate,
            multi_frame_enabled=multi_frame_enabled,
            max_observations_per_camera=max_observations_per_camera,
        )
        weights = AssociationWeights(
            plate_similarity=w_plate,
            reid_similarity=w_reid,
            vehicle_type_match=w_type,
            colour_match=w_colour,
            clm_plausibility=w_clm,
            timestamp_score=w_time,
            direction_match=w_dir,
            min_association_score=min_score,
        )
        run_simulation(settings, weights)

    if reset_clicked:
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════
#  MAIN CONTENT
# ═══════════════════════════════════════════════════════════════════════

# Header
st.markdown("""
<div class="main-header">
    <h1>🚗 SmartCity ANPR Trajectory Engine</h1>
    <p>City-Wide Automatic Number Plate Recognition — Synthetic Simulation & Analytics Dashboard</p>
</div>
""", unsafe_allow_html=True)

if not st.session_state.simulation_run:
    st.markdown("""
    <div class="info-box">
        <b>Welcome!</b> Configure simulation parameters in the sidebar and click
        <b>Run Simulation</b> to generate synthetic vehicles, camera detections,
        cross-camera associations, and trajectory reconstructions.
        <br><br>
        This simulation demonstrates how a centralised AI system can associate
        vehicle sightings across multiple ANPR cameras and reconstruct probable
        trajectories — using <b>entirely synthetic data</b>.
    </div>
    """, unsafe_allow_html=True)

    # Show the camera network even before simulation
    st.markdown('<div class="section-header">📷 SmartCity Camera Network (Default)</div>',
                unsafe_allow_html=True)

    default_graph = CameraGraph(DEFAULT_CAMERAS)
    viz = MapVisualizer(default_graph)
    try:
        from streamlit_folium import st_folium
        network_map = viz.create_camera_network_map(zoom_start=15)
        st_folium(network_map, width=None, height=500, key="pre_network_map")
    except Exception as e:
        st.warning(f"Map rendering unavailable: {e}")

    st.markdown('<div class="section-header">Saved Vehicle Trajectories</div>',
                unsafe_allow_html=True)
    st.caption(
        "Search trajectories from earlier simulation runs by reconstructed ID or "
        "synthetically recognized plate."
    )
    render_saved_trajectory_lookup(trajectory_store.list_runs(), "saved_home")

    st.stop()


# ── Simulation has run — show all tabs ──────────────────────────────────

vehicles = st.session_state.vehicles
detections = st.session_state.detections
det_df = st.session_state.detections_df
det_map = st.session_state.det_map
camera_graph = st.session_state.camera_graph
trajectories = st.session_state.trajectories
eval_results = st.session_state.eval_results
records_all = st.session_state.association_records

# Top metrics row
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-value">{len(vehicles)}</div>
        <div class="metric-label">GT Vehicles</div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-value">{len(detections)}</div>
        <div class="metric-label">Detections</div>
    </div>""", unsafe_allow_html=True)
with c3:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-value">{camera_graph.num_cameras()}</div>
        <div class="metric-label">Cameras</div>
    </div>""", unsafe_allow_html=True)
with c4:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-value">{len(trajectories)}</div>
        <div class="metric-label">Trajectories</div>
    </div>""", unsafe_allow_html=True)
with c5:
    combined_eval = eval_results.get("combined")
    f1_val = combined_eval.f1_score if combined_eval else 0
    st.markdown(f"""<div class="metric-card">
        <div class="metric-value">{f1_val:.2f}</div>
        <div class="metric-label">F1 Score</div>
    </div>""", unsafe_allow_html=True)
with c6:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-value">{st.session_state.processing_time:.1f}s</div>
        <div class="metric-label">Processing Time</div>
    </div>""", unsafe_allow_html=True)

st.markdown("")

# ── Tabs ────────────────────────────────────────────────────────────────

tab_network, tab_detections, tab_association, tab_trajectory, tab_analytics = st.tabs([
    "📷 Camera Network",
    "🔍 Detection Monitor",
    "🔗 Cross-Camera Association",
    "🗺️ Trajectory Explorer",
    "📊 Analytics & Evaluation",
])


# ── TAB 1: Camera Network ──────────────────────────────────────────────
with tab_network:
    st.markdown('<div class="section-header">Camera Network — SmartCity</div>',
                unsafe_allow_html=True)

    viz = MapVisualizer(camera_graph)

    try:
        from streamlit_folium import st_folium
        network_map = viz.create_camera_network_map(zoom_start=15)
        st_folium(network_map, width=None, height=550, key="network_map")
    except Exception as e:
        st.warning(f"Map rendering issue: {e}")

    st.markdown("#### Camera Details")
    cam_data = []
    expected_camera_passes = Counter(
        camera_id for vehicle in vehicles for camera_id in vehicle.route
    )
    for cam_id in camera_graph.get_all_camera_ids():
        cam = camera_graph.get_camera(cam_id)
        if cam:
            # Count detections at this camera
            cam_dets = sum(1 for d in detections if d.camera_id == cam_id)
            expected_passes = expected_camera_passes[cam_id]
            missed_detections = max(0, expected_passes - cam_dets)
            cam_data.append({
                "Camera ID": cam.camera_id,
                "Name": cam.name,
                "Latitude": cam.latitude,
                "Longitude": cam.longitude,
                "Entry Dirs": ", ".join(cam.entry_directions),
                "Exit Dirs": ", ".join(cam.exit_directions),
                "Connected To": ", ".join(cam.connected_cameras),
                "Configured Miss Rate": st.session_state.settings.camera_detection_failure_rates.get(
                    cam_id, st.session_state.settings.detection_failure_rate
                ),
                "Expected Passes": expected_passes,
                "Detections": cam_dets,
                "Missed Detections": missed_detections,
                "Observed Miss Rate": round(
                    missed_detections / expected_passes, 3
                ) if expected_passes else 0.0,
            })
    st.dataframe(pd.DataFrame(cam_data), use_container_width=True, hide_index=True)

    st.markdown("#### Graph Edges & Expected Travel Times")
    edge_data = []
    for src, dst, data in camera_graph.get_all_edges():
        edge_data.append({
            "From": src,
            "To": dst,
            "Transition Probability": data["transition_probability"],
            "Mean Travel Time (s)": data["mean_travel_time"],
            "Std Dev (s)": data["std_travel_time"],
        })
    st.dataframe(pd.DataFrame(edge_data), use_container_width=True, hide_index=True)


# ── TAB 2: Detection Monitor ───────────────────────────────────────────
with tab_detections:
    st.markdown('<div class="section-header">Detection Monitor</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="info-box">Showing synthetic camera detections. '
                'Ground-truth vehicle IDs are stored separately for evaluation only.</div>',
                unsafe_allow_html=True)

    # Filters
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        cam_filter = st.multiselect(
            "Filter by Camera",
            options=camera_graph.get_all_camera_ids(),
            default=[],
            key="det_cam_filter",
        )
    with col_f2:
        type_filter = st.multiselect(
            "Filter by Vehicle Type",
            options=sorted(det_df["vehicle_type"].unique()),
            default=[],
            key="det_type_filter",
        )
    with col_f3:
        conf_threshold = st.slider("Min OCR Confidence", 0.0, 1.0, 0.0, 0.05, key="det_conf")

    filtered_df = det_df.copy()
    if cam_filter:
        filtered_df = filtered_df[filtered_df["camera_id"].isin(cam_filter)]
    if type_filter:
        filtered_df = filtered_df[filtered_df["vehicle_type"].isin(type_filter)]
    filtered_df = filtered_df[filtered_df["ocr_confidence"] >= conf_threshold]

    st.markdown(f"**Showing {len(filtered_df)} of {len(det_df)} detections**")

    # Display columns without ground truth
    display_cols = [c for c in filtered_df.columns if "EVAL" not in c]
    st.dataframe(
        filtered_df[display_cols].head(200),
        use_container_width=True,
        hide_index=True,
    )

    # Re-ID similarity comparison tool
    st.markdown("#### 🔬 Re-ID Similarity Comparison")
    det_ids_list = [d.detection_id for d in detections[:200]]
    col_a, col_b = st.columns(2)
    with col_a:
        det_a_id = st.selectbox("Detection A", det_ids_list, key="reid_a")
    with col_b:
        det_b_id = st.selectbox("Detection B", det_ids_list, index=min(1, len(det_ids_list)-1), key="reid_b")

    if det_a_id and det_b_id and det_a_id in det_map and det_b_id in det_map:
        det_a = det_map[det_a_id]
        det_b = det_map[det_b_id]
        scores = SimilarityScorer.compute_all(det_a, det_b)

        score_df = pd.DataFrame([{
            "Metric": k.replace("_", " ").title(),
            "Score": f"{v:.4f}"
        } for k, v in scores.items()])
        st.dataframe(score_df, use_container_width=True, hide_index=True)

        same_vehicle = det_a.ground_truth_vehicle_id == det_b.ground_truth_vehicle_id
        st.markdown(
            f"*[Evaluation only]* Same ground-truth vehicle: "
            f"{'✅ Yes' if same_vehicle else '❌ No'}"
        )


# ── TAB 3: Cross-Camera Association ────────────────────────────────────
with tab_association:
    st.markdown('<div class="section-header">Cross-Camera Vehicle Association</div>',
                unsafe_allow_html=True)

    method_select = st.selectbox(
        "Association Method",
        ["combined", "plate_only", "reid_only"],
        key="assoc_method",
    )

    records = records_all.get(method_select, [])

    # Summary
    accepted_count = sum(1 for r in records if r.decision == "accepted")
    rejected_count = sum(1 for r in records if r.decision == "rejected")
    uncertain_count = sum(1 for r in records if r.decision == "uncertain")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Pairs Evaluated", len(records))
    with c2:
        st.metric("Accepted", accepted_count)
    with c3:
        st.metric("Rejected", rejected_count)
    with c4:
        st.metric("Uncertain", uncertain_count)

    # Show accepted associations
    st.markdown("#### Accepted Associations (Top 100)")
    accepted_records = [r for r in records if r.decision == "accepted"]
    accepted_records.sort(key=lambda r: r.final_score, reverse=True)

    if accepted_records:
        assoc_rows = []
        for r in accepted_records[:100]:
            d_a = det_map.get(r.detection_a_id)
            d_b = det_map.get(r.detection_b_id)
            assoc_rows.append({
                "Det A": r.detection_a_id[:12],
                "Camera A": d_a.camera_id if d_a else "?",
                "Plate A": d_a.recognised_plate if d_a else "?",
                "Det B": r.detection_b_id[:12],
                "Camera B": d_b.camera_id if d_b else "?",
                "Plate B": d_b.recognised_plate if d_b else "?",
                "Plate Sim": round(r.component_scores.get("plate_similarity", 0), 3),
                "ReID Sim": round(r.component_scores.get("reid_similarity", 0), 3),
                "CLM": round(r.component_scores.get("clm_plausibility", 0), 3),
                "Path Prior": r.clm_result.transition_probability if r.clm_result else 0.0,
                "Final Score": r.final_score,
                "Correct": "✅" if (d_a and d_b and d_a.ground_truth_vehicle_id == d_b.ground_truth_vehicle_id) else "❌",
            })
        st.dataframe(pd.DataFrame(assoc_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No accepted associations with this method.")

    # Detailed record viewer
    with st.expander("🔍 View Detailed Association Record"):
        if accepted_records:
            rec_idx = st.slider("Record index", 0, min(len(accepted_records)-1, 99), 0, key="rec_idx")
            rec = accepted_records[rec_idx]
            st.json({
                "detection_a": rec.detection_a_id,
                "detection_b": rec.detection_b_id,
                "component_scores": {k: round(v, 4) for k, v in rec.component_scores.items()},
                "final_score": rec.final_score,
                "decision": rec.decision,
                "method": rec.method,
                "explanation": rec.explanation,
                "clm_explanation": rec.clm_result.explanation if rec.clm_result else "N/A",
            })


# ── TAB 4: Trajectory Explorer ─────────────────────────────────────────
with tab_trajectory:
    st.markdown('<div class="section-header">Trajectory Explorer</div>',
                unsafe_allow_html=True)
    st.info(
        "To inspect one car, run the simulation, find its recognized plate in the "
        "Detection Monitor, then choose the matching plate in the trajectory list below. "
        "For a direct plate search, use Search Persisted Vehicle History at the bottom "
        "of this tab. This is a completed synthetic run, not live tracking."
    )
    st.markdown('<div class="info-box">Select a reconstructed trajectory to view '
                'its camera sequence, timing, and estimated route on the map. '
                'Inferred segments are <b>not confirmed paths</b>.</div>',
                unsafe_allow_html=True)

    if trajectories:
        # Build summary for selection
        traj_options = []
        for t in trajectories:
            plates = t.recognised_plates
            common_plate = max(set(plates), key=plates.count) if plates else "?"
            traj_options.append(
                f"{t.trajectory_id} | {common_plate} | "
                f"{len(t.detection_ids)} dets | "
                f"Conf: {t.overall_confidence:.2f}"
            )

        selected_idx = st.selectbox(
            "Select trajectory (type a plate or trajectory ID to search)",
            range(len(traj_options)),
            format_func=lambda i: traj_options[i],
            key="traj_select",
            help="Each option shows the reconstructed trajectory ID, its most common recognized plate, and its number of sightings.",
        )

        traj = trajectories[selected_idx]

        # Info columns
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Detections", len(traj.detection_ids))
        with c2:
            st.metric("Confidence", f"{traj.overall_confidence:.2f}")
        with c3:
            st.metric("Inferred Segments", traj.num_inferred)
        with c4:
            st.metric("Uncertain Segments", traj.num_uncertain)

        # Camera sequence
        st.markdown("#### Camera Sequence")
        seq_data = []
        base_time = datetime(2024, 1, 15, 8, 0, 0)
        for i, (cam, ts, plate) in enumerate(
            zip(traj.camera_sequence, traj.timestamps, traj.recognised_plates)
        ):
            dt = base_time + timedelta(seconds=ts)
            seq_data.append({
                "Step": i + 1,
                "Camera": cam,
                "Camera Name": camera_graph.get_camera(cam).name if camera_graph.get_camera(cam) else "?",
                "Time": dt.strftime("%H:%M:%S"),
                "Plate": plate,
            })
        st.dataframe(pd.DataFrame(seq_data), use_container_width=True, hide_index=True)

        # Segment details
        if traj.segments:
            st.markdown("#### Segment Analysis")
            seg_data = []
            for seg in traj.segments:
                seg_data.append({
                    "From": seg.from_camera,
                    "To": seg.to_camera,
                    "Elapsed (s)": round(seg.elapsed_seconds, 1),
                    "Type": seg.segment_type,
                    "Confidence": seg.confidence,
                    "Explanation": seg.explanation,
                })
            st.dataframe(pd.DataFrame(seg_data), use_container_width=True, hide_index=True)

        # Map
        st.markdown("#### Route Map")
        viz = MapVisualizer(camera_graph)
        use_osrm_current = st.checkbox(
            "Try OSM road routing (public OSRM service)",
            value=False,
            help="Sends the hypothetical camera coordinates to OSRM. If routing fails, the map uses a labelled straight-line fallback.",
            key="current_traj_osrm",
        )
        try:
            from streamlit_folium import st_folium
            traj_map = viz.create_trajectory_map(
                traj, det_map, zoom_start=15, use_osrm=use_osrm_current
            )
            st_folium(traj_map, width=None, height=550, key="traj_map")
        except Exception as e:
            st.warning(f"Map rendering issue: {e}")

        # Ground truth comparison (evaluation only)
        with st.expander("📊 Ground-Truth Comparison (Evaluation Only)"):
            st.markdown(
                f"**Ground-truth vehicle IDs in this trajectory:** "
                f"{', '.join(traj.ground_truth_vehicle_ids)}"
            )
            is_pure = len(traj.ground_truth_vehicle_ids) == 1
            st.markdown(
                f"**Trajectory purity:** {'✅ Pure (single vehicle)' if is_pure else '⚠️ Mixed (multiple vehicles)'}"
            )
    else:
        st.info("No trajectories reconstructed. Run the simulation first.")

    st.markdown("#### Search Persisted Vehicle History")
    st.caption(
        "Saved sightings remain available after the Streamlit session ends. "
        "Search by reconstructed trajectory ID or recognized plate text."
    )
    render_saved_trajectory_lookup(trajectory_store.list_runs(), "saved_explorer")


# ── TAB 5: Analytics & Evaluation ──────────────────────────────────────
with tab_analytics:
    st.markdown('<div class="section-header">Analytics & Evaluation</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="disclaimer-box">⚠️ All metrics are computed against '
                'synthetic ground truth. These are NOT real-world performance results.</div>',
                unsafe_allow_html=True)

    if eval_results:
        st.caption(
            f"Tracking reconstructs trajectories from all {st.session_state.tracking_detection_count:,} "
            f"generated detections. Comparison metrics use an even timeline sample of "
            f"{st.session_state.evaluation_detection_count:,} detections so all three "
            "methods can be compared consistently."
        )
        st.caption(
            "Association precision and recall count exact consecutive detection links; "
            "trajectory completeness is the fraction of ground-truth links recovered."
        )
        if st.session_state.export_dir:
            export_path = Path(st.session_state.export_dir)
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for artifact in export_path.iterdir():
                    if artifact.is_file():
                        archive.write(artifact, arcname=artifact.name)
            st.success(f"Scenario artifacts saved to `{export_path.relative_to(Path(__file__).parent)}`")
            st.download_button(
                "Download scenario export (ZIP)",
                data=zip_buffer.getvalue(),
                file_name=f"{export_path.name}.zip",
                mime="application/zip",
            )
        # Method comparison table
        st.markdown("#### Method Comparison")
        evaluator = EvaluationEngine()
        comparison = evaluator.compare_methods(eval_results)
        comp_df = pd.DataFrame(comparison)
        st.dataframe(comp_df, use_container_width=True, hide_index=True)

        # Detailed metrics for combined method
        st.markdown("#### Combined Method — Detailed Metrics")
        combined = eval_results.get("combined")
        if combined:
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Precision", f"{combined.precision:.4f}")
            with m2:
                st.metric("Recall", f"{combined.recall:.4f}")
            with m3:
                st.metric("F1 Score", f"{combined.f1_score:.4f}")
            with m4:
                st.metric("Trajectory Completeness", f"{combined.trajectory_completeness:.4f}")

            m5, m6, m7, m8 = st.columns(4)
            with m5:
                st.metric("Incorrect Transition Rate", f"{combined.false_match_rate:.4f}")
            with m6:
                st.metric("Missed Transition Rate", f"{combined.missed_association_rate:.4f}")
            with m7:
                st.metric("Correct Assoc.", combined.correct_associations)
            with m8:
                st.metric("Incorrect Assoc.", combined.incorrect_associations)

        # Bar chart comparison
        st.markdown("#### Performance Comparison Across Methods")
        chart_data = pd.DataFrame({
            "Method": [r["Method"] for r in comparison],
            "Precision": [r["Precision"] for r in comparison],
            "Recall": [r["Recall"] for r in comparison],
            "F1": [r["F1"] for r in comparison],
        }).set_index("Method")
        st.bar_chart(chart_data)

        st.markdown("#### OCR and Re-ID Sensitivity")
        st.caption(
            "The sweep reuses one synthetic vehicle fleet across settings. "
            "All three methods use the same detections at each setting; each "
            "variant evaluates at most 180 detections from a fleet of at most 75 vehicles."
        )
        if st.button("Run sensitivity sweep", key="run_sensitivity_sweep"):
            with st.spinner("Running reproducible synthetic sensitivity scenarios..."):
                try:
                    st.session_state.sensitivity_results = run_sensitivity_analysis(
                        st.session_state.settings, st.session_state.weights
                    )
                except Exception as exc:
                    st.session_state.sensitivity_results = None
                    st.error(f"Sensitivity analysis could not complete: {exc}")

        if st.session_state.sensitivity_results:
            sensitivity_df = pd.DataFrame(st.session_state.sensitivity_results)
            for parameter in sensitivity_df["Parameter"].drop_duplicates():
                st.markdown(f"**F1 by {parameter}**")
                parameter_df = sensitivity_df[
                    sensitivity_df["Parameter"] == parameter
                ]
                f1_chart = parameter_df.pivot(
                    index="Level", columns="Method", values="F1"
                ).sort_index()
                st.line_chart(f1_chart)
                st.dataframe(
                    parameter_df.drop(columns=["Parameter"]),
                    use_container_width=True,
                    hide_index=True,
                )

        # Detection distribution by camera
        st.markdown("#### Detection Distribution by Camera")
        cam_counts = Counter(d.camera_id for d in detections)
        cam_chart = pd.DataFrame({
            "Camera": list(cam_counts.keys()),
            "Detections": list(cam_counts.values()),
        }).set_index("Camera")
        st.bar_chart(cam_chart)

        # Trajectory purity analysis
        st.markdown("#### Trajectory Purity Analysis")
        if combined and combined.per_vehicle_details:
            purity_df = pd.DataFrame(combined.per_vehicle_details)
            st.dataframe(purity_df.head(50), use_container_width=True, hide_index=True)

            pure_count = sum(1 for d in combined.per_vehicle_details if d.get("is_pure"))
            total_trajs = len(combined.per_vehicle_details)
            st.metric(
                "Pure Trajectories",
                f"{pure_count}/{total_trajs} "
                f"({pure_count/total_trajs*100:.1f}%)" if total_trajs > 0 else "N/A"
            )

        # OCR error impact analysis
        st.markdown("#### Summary Statistics")
        summary_data = {
            "Metric": [
                "Total ground-truth vehicles",
                "Total detections generated",
                "Injected out-of-order timestamps (evaluation only)",
                "Detection failure rate (configured)",
                "OCR error rate (configured)",
                "Re-ID noise level (configured)",
                "Processing time (seconds)",
                "Detections per vehicle (avg)",
            ],
            "Value": [
                len(vehicles),
                len(detections),
                sum(1 for detection in detections if detection.is_timestamp_order_anomaly),
                f"{st.session_state.settings.detection_failure_rate:.2%}",
                f"{st.session_state.settings.ocr_error_rate:.2%}",
                f"{st.session_state.settings.reid_noise_level:.2f}",
                f"{st.session_state.processing_time:.2f}",
                f"{len(detections)/len(vehicles):.1f}" if vehicles else "N/A",
            ],
        }
        st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)

        st.markdown("#### Processing Time by Pipeline Stage")
        st.caption(
            "Stage timings are measured for this run. The association stages use "
            f"the evaluated subset of {st.session_state.evaluation_detection_count:,} "
            f"of {len(detections):,} generated detections."
        )
        stage_df = pd.DataFrame([
            {"Stage": stage, "Seconds": round(seconds, 4)}
            for stage, seconds in st.session_state.processing_stage_times.items()
        ])
        if not stage_df.empty:
            st.dataframe(stage_df, use_container_width=True, hide_index=True)
            st.bar_chart(stage_df.set_index("Stage"))
    else:
        st.info("Run the simulation to see evaluation metrics.")


# ── Footer ──────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<div style="text-align:center; color:#8892b0; font-size:0.8rem;">'
    'SmartCity ANPR Trajectory Engine — Synthetic Simulation v1.0<br>'
    'All data is synthetic. No real surveillance or personal data is used.'
    '</div>',
    unsafe_allow_html=True,
)
