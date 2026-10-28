# SmartCity ANPR Trajectory Simulation

An end-to-end **synthetic** simulation of camera detections, cross-camera
association, trajectory reconstruction, and evaluation. It does not process
real camera footage and does not run trained OCR, detection, or Re-ID models.

## Run the dashboard

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Use the sidebar to configure the vehicle count, simulation window, random seed,
and synthetic error levels, then start the simulation. The dashboard compares
plate-only, synthetic Re-ID-only, and combined association against the
simulation's ground truth.

Regenerate the checked-in example scenario without starting the dashboard:

```powershell
python -m src.utils.generate_example_scenario
```

The included example uses 24 synthetic vehicles, an eight-camera network, and
a fixed seed. Ground-truth columns are explicitly marked evaluation-only.

## Pipeline

1. `config/settings.py` defines simulation settings and the hypothetical
   SmartCity camera layout.
2. `src/camera_network/` builds a directed graph and scores transitions using
   expected travel times and normalized outgoing-edge transition probabilities.
3. `src/simulation/` generates synthetic vehicles, graph-constrained routes,
   and imperfect camera detections.
4. `src/anpr/` and `src/reid/` simulate plate OCR and appearance embeddings.
5. `src/association/` scores candidate sighting pairs and uses a maximum-weight
   assignment to build non-branching trajectories without using ground-truth
   IDs as matching evidence. Large tracking runs use conservative camera/time
   candidate windows and solve disconnected assignment components separately.
   Combined evidence weights are normalized before scoring; an all-zero weight
   set cannot produce a match.
6. `src/trajectory/` labels observed, inferred, and uncertain segments.
7. `src/mapping/` renders camera and trajectory views with Folium.
8. `src/evaluation/` compares reconstructed associations to synthetic truth.
9. `app.py` presents controls, maps, detection and association views, and
   evaluation results in Streamlit.
10. `src/storage/trajectory_store.py` stores run detections and reconstructed
    camera-coordinate sightings in SQLite for later search.

Simulation settings and association weights are validated when constructed.
The association engine also rejects duplicate detection IDs, unknown cameras,
invalid confidences/timestamps, malformed embeddings, and unsupported method
names with a specific `ValueError` before scoring begins.

## Project layout

```text
app.py
requirements.txt
README.md
config/                 Settings and default camera layout
data/generated/         Example scenario and per-run exports
src/anpr/               Synthetic OCR
src/association/        Similarity scoring and association engine
src/camera_network/     Directed graph and camera-link model
src/evaluation/         Synthetic-ground-truth metrics
src/mapping/            Folium maps
src/reid/                Synthetic appearance embeddings
src/simulation/         City, vehicle, and detection generation
src/trajectory/         Trajectory reconstruction
src/utils/              Logging helpers
tests/                  Unit tests for core modules
```

## Current limitations

- The camera-count control selects a connected subset of the designed layout
  (4–8 cameras) or extends the hypothetical southbound corridor (9–16).
- Completed runs are stored in `data/smartcity_trajectories.sqlite3`. Search
  saved trajectories by reconstructed trajectory ID or recognized plate from
  the welcome screen or Trajectory Explorer. If a plate search has no
  reconstructed trajectory, the lookup also searches all saved raw camera
  detections and displays their observed camera coordinates without linking
  them into a vehicle path. Run history shows vehicle, detection, camera, and
  reconstructed trajectory counts for the 20 most recent runs. Search result
  limits are shown in the interface. Ground-truth labels are stored in a
  separate evaluation table.
- The sidebar can enable multi-frame OCR fusion and control the maximum frame
  count. It can also inject an unexpected timestamp order at a selected rate;
  the true route index and anomaly marker are evaluation-only and are excluded
  from matching features.
- A global detection failure rate applies to all cameras; overrides can be set
  per camera. Camera activity reports expected passes, observed detections, and
  observed misses for the generated scenario.
- Similar-looking synthetic vehicles can be introduced with a configurable
  appearance rate. Their embeddings remain distinct but are sampled near an
  earlier vehicle's appearance vector to create plausible Re-ID ambiguity.
- The map uses hypothetical coordinates and OpenStreetMap tiles. It does not
  retrieve a complete local road network. The Trajectory Explorer can request
  route geometry from the public OSRM service; it falls back to a labelled
  straight line when routing is unavailable. Either geometry is only an
  estimate and does not confirm the vehicle's actual path.
- `data/generated/` receives a per-run export containing synthetic vehicle and
  detection tables, association decisions, trajectories, embeddings, settings,
  and evaluation metrics. Combined trajectories cover the full generated run;
  plate-only and Re-ID-only trajectories, association decisions, and all
  comparison metrics use the shared evaluation sample. The export metadata
  records these scopes and detection counts. Exports can also be downloaded as
  ZIP files from Analytics.
- Association uses pairwise scores followed by a maximum-weight predecessor/
  successor assignment. It does not optimize a full trajectory-level score.
- Three-method comparison and metrics use an even timestamp sample capped at
  500 detections so methods share one evaluation set. Combined trajectory
  tracking and SQLite persistence process every generated detection. The
  dashboard and scenario metadata report both counts separately.
- Full-run tracking uses a conservative CLM time-window prefilter and solves
  maximum-weight assignments independently within connected candidate groups,
  avoiding a single dense assignment matrix for the entire run. Evaluation
  views retain every candidate decision on the bounded comparison sample.
- Pair iteration skips detections outside the configured time horizon, Re-ID
  cosine scores use a NumPy dot product, and camera path profiles are prepared
  once per graph instead of recomputed for every pair.
- Analytics reports per-stage processing time for camera/vehicle/detection
  generation, each association method, trajectory reconstruction, SQLite
  persistence, evaluation, and scenario export. Association timings apply to
  the evaluated subset when a run exceeds the 500-detection cap.

All maps, detections, match scores, and metrics are illustrative synthetic
outputs, not real-world identification or performance claims.

Evaluation precision and recall are based on exact consecutive detection-ID
links. A link is correct only when those two specific detections are adjacent
in the true route sequence for the same synthetic vehicle. Precision is
`TP / (TP + FP)`, recall is `TP / (TP + FN)`, and F1 is their harmonic mean.
Incorrect transition rate is `FP / (TP + FP)`; missed transition rate is
`FN / (TP + FN)`. Trajectory completeness equals recall. Undefined zero-
denominator rates are reported as zero.

The Analytics tab also offers OCR-error and Re-ID-noise sensitivity sweeps at
0.0, 0.1, 0.2, and 0.3. Each sweep reuses one synthetic fleet and compares
combined, plate-only, and Re-ID-only association on the same detections per
setting. To keep the interactive sweep responsive, it uses up to 75 vehicles
and evaluates up to 180 detections per setting.

## Model integration roadmap

1. Keep the `Detection` contract and replace synthetic plate observations with
   a real vehicle detector and pretrained OCR adapter; retain OCR confidence
   and multiple plate hypotheses.
2. Replace synthetic appearance vectors with a pretrained vehicle Re-ID
   adapter that emits normalized embeddings. Do not use dataset identities as
   live matching features.
3. Calibrate the camera graph and travel-time distributions using approved
   operational data; preserve the uncertainty-aware association interface.
4. Add access controls, retention limits, audit trails, and database migrations
   before storing real camera data. The current SQLite database is for this
   synthetic demonstration only.
