"""Optional OSRM routing for illustrative camera-to-camera map geometry."""

from functools import lru_cache
import json
from typing import List, Optional, Tuple
from urllib.error import URLError
from urllib.request import Request, urlopen


@lru_cache(maxsize=2048)
def _fetch_osrm_route(
    start_latitude: float,
    start_longitude: float,
    end_latitude: float,
    end_longitude: float,
) -> Optional[Tuple[Tuple[float, float], ...]]:
    """Return OSRM geometry as (latitude, longitude) pairs, or None."""
    coordinates = (
        f"{start_longitude:.6f},{start_latitude:.6f};"
        f"{end_longitude:.6f},{end_latitude:.6f}"
    )
    url = (
        f"https://router.project-osrm.org/route/v1/driving/{coordinates}"
        "?overview=full&geometries=geojson&steps=false"
    )
    request = Request(url, headers={"User-Agent": "SmartCity-ANPR-Simulation/1.0"})
    try:
        with urlopen(request, timeout=4) as response:
            payload = json.loads(response.read(2_000_000).decode("utf-8"))
    except (OSError, URLError, TimeoutError, ValueError):
        return None

    routes = payload.get("routes") or []
    if payload.get("code") != "Ok" or not routes:
        return None
    geometry = routes[0].get("geometry", {}).get("coordinates", [])
    if len(geometry) < 2:
        return None
    # GeoJSON coordinate order is [longitude, latitude].
    return tuple((float(lat), float(lon)) for lon, lat in geometry)


def get_osrm_route(
    start: Tuple[float, float],
    end: Tuple[float, float],
) -> Optional[List[List[float]]]:
    """Get a cached driving route for (latitude, longitude) endpoints."""
    result = _fetch_osrm_route(
        round(float(start[0]), 6), round(float(start[1]), 6),
        round(float(end[0]), 6), round(float(end[1]), 6),
    )
    return [list(point) for point in result] if result else None
