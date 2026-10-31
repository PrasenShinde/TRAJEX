import React, { useEffect, useRef } from 'react';
import { Deck, MapView as DeckMapView } from '@deck.gl/core';
import { PathLayer, ScatterplotLayer } from '@deck.gl/layers';
import type { Engine } from '../sim/engine';

export type MapViewProps = {
  engine: Engine;
  playing: boolean;
  speed: number;
  overlays: any[]; // layers drawn above roads, below cars
  topOverlays?: any[];
  selectedCarId: string | null;
  suggestedNode?: string | null;
  onJunctionClick: (nodeId: string) => void;
  onCarClick: (carId: string) => void;
  onTick: () => void;
  children?: React.ReactNode;
};

export function MapView(props: MapViewProps) {
  const host = useRef<HTMLDivElement>(null);
  const deckRef = useRef<Deck | null>(null);
  const propsRef = useRef(props);
  propsRef.current = props;

  useEffect(() => {
    const g = props.engine.graph;
    const lat = (g.minLat + g.maxLat) / 2, lon = (g.minLon + g.maxLon) / 2;
    const cosLat = Math.cos((lat * Math.PI) / 180);
    const spanM = Math.max((g.maxLat - g.minLat) * 111320, (g.maxLon - g.minLon) * 111320 * cosLat);
    const box = Math.min(host.current!.clientWidth || 800, host.current!.clientHeight || 700);
    const zoom = Math.log2((78271.5 * cosLat * 0.85 * box) / spanM);
    const deck = new Deck({
      parent: host.current!,
      views: new DeckMapView({ repeat: false }),
      initialViewState: { longitude: lon, latitude: lat, zoom, pitch: 0, bearing: 0 },
      controller: true,
      style: { position: 'absolute', inset: '0' } as any,
      getCursor: ({ isHovering }: any) => (isHovering ? 'pointer' : 'grab'),
      onClick: (info: any) => {
        const p = propsRef.current;
        if (info?.layer?.id === 'junctions' && info.object) p.onJunctionClick(info.object.id);
        else if (info?.layer?.id === 'cars' && info.object) p.onCarClick(info.object.id);
      },
      getTooltip: ({ object, layer }: any) => {
        if (!object) return null;
        if (layer?.id === 'junctions') return { text: `Junction ${object.id}\nclick: add/remove camera` };
        if (layer?.id === 'cars') return { text: object.id };
        return null;
      },
    } as any);
    deckRef.current = deck;

    const roadData = g.edges.map(e => ({ path: e.coords, hw: e.highway }));
    const junctionData = g.nodes.map(n => ({ id: n.id, pos: [n.lon, n.lat] as [number, number] }));
    const roads = new PathLayer({
      id: 'roads', data: roadData, getPath: (d: any) => d.path,
      getColor: (d: any) => (d.hw === 'primary' || d.hw === 'trunk' ? [110, 120, 135, 200] : [70, 78, 90, 200]),
      getWidth: (d: any) => (d.hw === 'primary' || d.hw === 'trunk' ? 5 : 3), widthUnits: 'meters', widthMinPixels: 1,
    });

    let raf = 0, last = performance.now(), lastTick = 0;
    const loop = (now: number) => {
      const p = propsRef.current;
      const dtReal = Math.min(0.1, (now - last) / 1000);
      last = now;
      if (p.playing) p.engine.step(dtReal * p.speed);
      const pos = p.engine.positions();
      const cams = p.engine.cameraList().map(c => {
        const n = g.nodes[g.nodeIdx.get(c.nodeId)!];
        return { id: c.id, pos: [n.lon, n.lat] as [number, number] };
      });
      const pulse = 1 + 0.35 * Math.sin(now / 220);
      const sug = p.suggestedNode ? g.nodes[g.nodeIdx.get(p.suggestedNode)!] : null;
      deck.setProps({
        layers: [
          roads,
          new ScatterplotLayer({
            id: 'junctions', data: junctionData, getPosition: (d: any) => d.pos, getRadius: 5, radiusUnits: 'meters',
            radiusMinPixels: 3, getFillColor: [90, 100, 115, 255], pickable: true,
          }),
          ...p.overlays,
          new ScatterplotLayer({
            id: 'cameras', data: cams, getPosition: (d: any) => d.pos, getRadius: 11, radiusUnits: 'pixels',
            stroked: true, filled: true, getFillColor: [76, 201, 240, 70], getLineColor: [76, 201, 240, 255], lineWidthMinPixels: 2,
          }),
          ...(sug ? [new ScatterplotLayer({
            id: 'suggested', data: [{ pos: [sug.lon, sug.lat] }], getPosition: (d: any) => d.pos,
            getRadius: 16 * pulse, radiusUnits: 'pixels', stroked: true, filled: true,
            getFillColor: [250, 204, 21, 60], getLineColor: [250, 204, 21, 255], lineWidthMinPixels: 3,
            updateTriggers: { getRadius: [pulse] },
          })] : []),
          new ScatterplotLayer({
            id: 'cars', data: pos, getPosition: (d: any) => d.pos, getRadius: 4, radiusUnits: 'pixels',
            getFillColor: (d: any) => [...d.colour, 255] as any, pickable: true,
            updateTriggers: { getPosition: [p.engine.t], getFillColor: [p.engine.cars.length] },
          }),
          ...(p.selectedCarId ? [new ScatterplotLayer({
            id: 'selected', data: pos.filter(c => c.id === p.selectedCarId), getPosition: (d: any) => d.pos,
            getRadius: 11, radiusUnits: 'pixels', stroked: true, filled: false, getLineColor: [250, 204, 21, 255],
            lineWidthMinPixels: 3, updateTriggers: { getPosition: [p.engine.t] },
          })] : []),
          ...(p.topOverlays ?? []),
        ],
      });
      if (now - lastTick > 250) { lastTick = now; p.onTick(); }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => { cancelAnimationFrame(raf); deck.finalize(); deckRef.current = null; };
    // engine instance change => rebuild deck (new graph/viewport)
  }, [props.engine]);

  return <div className="center" ref={host}>{props.children}</div>;
}
