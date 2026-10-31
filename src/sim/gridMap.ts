import type { Edge, MapData, Node } from './types';

const CENTER_LAT = 12.935;
const CENTER_LON = 77.626;
const M_PER_DEG_LAT = 111320;

/** 8x8 junctions, 300 m blocks, a few one-way streets and two arterials. */
export function makeGridMap(size = 8, block = 300): MapData {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const mLon = M_PER_DEG_LAT * Math.cos((CENTER_LAT * Math.PI) / 180);
  const half = ((size - 1) * block) / 2;
  const id = (r: number, c: number) => `g${r}_${c}`;
  for (let r = 0; r < size; r++)
    for (let c = 0; c < size; c++)
      nodes.push({
        id: id(r, c),
        lat: CENTER_LAT + (half - r * block) / M_PER_DEG_LAT, // r=0 is north
        lon: CENTER_LON + (c * block - half) / mLon,
      });
  const byId = new Map(nodes.map(n => [n.id, n]));
  // Arterials: row 3 and column 4. One-way: rows 1 (east), 6 (west); cols 2 (south), 5 (north).
  const speedFor = (r1: number, c1: number, r2: number, c2: number): [number, string] => {
    const horizontal = r1 === r2;
    if (horizontal && r1 === 3) return [35, 'primary'];
    if (!horizontal && c1 === 4) return [35, 'primary'];
    if ((horizontal && (r1 === 1 || r1 === 6)) || (!horizontal && (c1 === 2 || c1 === 5))) return [25, 'tertiary'];
    return [20, 'residential'];
  };
  const add = (r1: number, c1: number, r2: number, c2: number, oneway: boolean) => {
    const a = byId.get(id(r1, c1))!, b = byId.get(id(r2, c2))!;
    const [spd, hw] = speedFor(r1, c1, r2, c2);
    edges.push({
      id: `${a.id}>${b.id}`, u: a.id, v: b.id, lengthM: block, speedKph: spd, highway: hw, oneway,
      coords: [[a.lon, a.lat], [b.lon, b.lat]],
    });
  };
  for (let r = 0; r < size; r++)
    for (let c = 0; c < size; c++) {
      if (c + 1 < size) { // horizontal r,c -> r,c+1
        if (r === 1) add(r, c, r, c + 1, true); // east only
        else if (r === 6) add(r, c + 1, r, c, true); // west only
        else { add(r, c, r, c + 1, false); add(r, c + 1, r, c, false); }
      }
      if (r + 1 < size) { // vertical r,c -> r+1,c  (r+1 is south)
        if (c === 2) add(r, c, r + 1, c, true); // south only
        else if (c === 5) add(r + 1, c, r, c, true); // north only
        else { add(r, c, r + 1, c, false); add(r + 1, c, r, c, false); }
      }
    }
  return { name: 'Grid city', nodes, edges };
}
