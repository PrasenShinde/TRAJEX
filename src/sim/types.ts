export type Node = { id: string; lat: number; lon: number };
export type Edge = {
  id: string;
  u: string;
  v: string;
  lengthM: number;
  speedKph: number;
  coords: [number, number][]; // [lon, lat]
  highway?: string;
  oneway?: boolean;
};
export type Camera = { id: string; nodeId: string; detectProb: number; ocrError?: number };
export type VehicleType = 'car' | 'suv' | 'auto' | 'bike' | 'bus';
export type Car = {
  id: string;
  plate: string; // 10 chars, e.g. KA01AB1234
  type: VehicleType;
  colour: string;
  route: string[]; // edge ids of the current trip
  speedFactor: number;
  departT: number;
  lookalikeOf?: string;
};
export type Sighting = {
  id: string;
  cameraId: string;
  nodeId: string;
  t: number;
  plateRead: string | null;
  plateConf: number;
  type: string;
  colour: string;
  heading: number; // degrees, 0 = north, clockwise
  trueCarId: string; // hidden from tracker
};
export type RouteHypothesis = { edgeIds: string[]; nodeIds: string[]; travelTimeS: number; prob: number };

export type MapData = { name: string; nodes: Node[]; edges: Edge[] };
