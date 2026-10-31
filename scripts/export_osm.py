"""One-time export of the Koramangala (Bengaluru) drive network to public/data/koramangala.json.

Usage:  .venv/bin/python scripts/export_osm.py
Needs:  pip install osmnx   (osmnx 2.x)
"""
import json
import sys
import time
from pathlib import Path

import networkx as nx
import osmnx as ox

WEST, SOUTH, EAST, NORTH = 77.612, 12.922, 77.640, 12.948
OUT = Path(__file__).resolve().parent.parent / "public" / "data" / "koramangala.json"
DEFAULT_KPH = {"motorway": 40, "trunk": 40, "primary": 35, "secondary": 30, "tertiary": 25}  # city traffic, not limits


def first(v):
    return v[0] if isinstance(v, list) else v


def speed_for(highway, maxspeed):
    hw = str(first(highway)).replace("_link", "")
    return DEFAULT_KPH.get(hw, 20)


def main():
    ox.settings.log_console = True
    ox.settings.requests_timeout = 60
    ox.settings.overpass_rate_limit = False
    print("downloading drive network from OpenStreetMap ...", flush=True)
    G = None
    endpoints = ["https://overpass-api.de/api", "https://overpass.kumi.systems/api", "https://overpass.private.coffee/api"]
    for attempt in range(8):
        ox.settings.overpass_url = endpoints[attempt % len(endpoints)]
        try:
            G = ox.graph_from_bbox(bbox=(WEST, SOUTH, EAST, NORTH), network_type="drive")
            break
        except Exception as ex:  # server busy etc.
            wait = min(60, 5 * 2 ** (attempt // 3))
            print(f"attempt {attempt + 1} via {ox.settings.overpass_url} failed ({type(ex).__name__}); retry in {wait}s", flush=True)
            time.sleep(wait)
    if G is None:
        sys.exit("OpenStreetMap download failed")
    print(f"raw: {len(G.nodes)} nodes, {len(G.edges)} edges", flush=True)
    Gp = ox.project_graph(G)
    Gc = ox.consolidate_intersections(Gp, tolerance=15, rebuild_graph=True, dead_ends=True)
    Gc = ox.project_graph(Gc, to_crs="EPSG:4326")  # back to lon/lat
    # keep largest strongly connected component so every car can reach every junction
    comp = max(nx.strongly_connected_components(Gc), key=len)
    Gc = Gc.subgraph(comp).copy()
    print(f"consolidated: {len(Gc.nodes)} nodes, {len(Gc.edges)} edges", flush=True)

    nodes, idmap = [], {}
    for i, (n, d) in enumerate(Gc.nodes(data=True)):
        idmap[n] = f"n{i}"
        nodes.append({"id": f"n{i}", "lat": round(d["y"], 6), "lon": round(d["x"], 6)})

    edges = []
    for k, (u, v, key, d) in enumerate(Gc.edges(keys=True, data=True)):
        if u == v:
            continue
        nu, nv = Gc.nodes[u], Gc.nodes[v]
        geom = d.get("geometry")
        coords = [[round(x, 6), round(y, 6)] for x, y in geom.coords] if geom is not None else []
        a, b = [nu["x"], nu["y"]], [nv["x"], nv["y"]]
        # geometry of consolidated edges may not touch the merged node centroids: anchor the ends
        if not coords:
            coords = [[round(a[0], 6), round(a[1], 6)], [round(b[0], 6), round(b[1], 6)]]
        else:
            coords[0] = [round(a[0], 6), round(a[1], 6)]
            coords[-1] = [round(b[0], 6), round(b[1], 6)]
        length = float(d.get("length", 0)) or 1.0
        hw = first(d.get("highway", "residential"))
        edges.append({
            "id": f"e{k}", "u": idmap[u], "v": idmap[v], "lengthM": round(length, 1),
            "speedKph": speed_for(hw, d.get("maxspeed")), "highway": str(hw),
            "oneway": bool(first(d.get("oneway", False))), "coords": coords,
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"nodes": nodes, "edges": edges}, separators=(",", ":")))
    print(f"wrote {OUT} ({len(nodes)} nodes, {len(edges)} edges, {OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    sys.exit(main())
