import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import { cameras, camById, edges } from '../data/mock'
import { posOf, headingOf, predict } from '../hooks/useSimulation'
const fc = f => ({ type: 'FeatureCollection', features: f })
const line = (c, p = {}) => ({ type: 'Feature', properties: p, geometry: { type: 'LineString', coordinates: c } })
export default function MapView({ vehicles, selected, onSelectVehicle, onSelectCamera }) {
  const el = useRef(), map = useRef(), mk = useRef({}), labels = useRef([]), ready = useRef(false), cb = useRef({})
  cb.current = { onSelectVehicle, onSelectCamera }
  useEffect(() => {
    const m = map.current = new maplibregl.Map({
      container: el.current, center: [77.024, 20.715], zoom: 12.6, attributionControl: false,
      style: { version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#0b0f14' } }] }
    })
    m.on('load', () => {
      m.addSource('roads', { type: 'geojson', data: fc(edges.map(e => line([[camById[e.a].lng, camById[e.a].lat], [camById[e.b].lng, camById[e.b].lat]], { lv: e.level }))) })
      m.addSource('cams', { type: 'geojson', data: fc(cameras.map(c => ({ type: 'Feature', properties: { id: c.id, s: c.status }, geometry: { type: 'Point', coordinates: [c.lng, c.lat] } }))) })
      m.addSource('obs', { type: 'geojson', data: fc([]) }); m.addSource('pred', { type: 'geojson', data: fc([]) })
      m.addLayer({ id: 'case', type: 'line', source: 'roads', paint: { 'line-color': '#1c2432', 'line-width': 9 } })
      m.addLayer({ id: 'road', type: 'line', source: 'roads', paint: { 'line-width': 3, 'line-color': ['match', ['get', 'lv'], 2, '#ef4444', 1, '#f59e0b', '#2a3548'], 'line-opacity': .8 } })
      m.addLayer({ id: 'cover', type: 'circle', source: 'cams', paint: { 'circle-radius': 38, 'circle-color': ['match', ['get', 's'], 'degraded', '#f59e0b', '#22c3e6'], 'circle-opacity': .07 } })
      m.addLayer({ id: 'pred', type: 'line', source: 'pred', paint: { 'line-color': '#22c3e6', 'line-dasharray': [2, 2], 'line-width': ['get', 'w'], 'line-opacity': ['get', 'op'] } })
      m.addLayer({ id: 'obs', type: 'line', source: 'obs', paint: { 'line-color': '#22c3e6', 'line-width': 4 } })
      m.addLayer({ id: 'cams', type: 'circle', source: 'cams', paint: { 'circle-radius': 7, 'circle-color': ['match', ['get', 's'], 'degraded', '#f59e0b', 'offline', '#ef4444', '#34d399'], 'circle-stroke-color': '#0a0d12', 'circle-stroke-width': 2 } })
      m.on('click', 'cams', e => cb.current.onSelectCamera(e.features[0].properties.id))
      m.on('mouseenter', 'cams', () => m.getCanvas().style.cursor = 'pointer'); m.on('mouseleave', 'cams', () => m.getCanvas().style.cursor = '')
      ready.current = true
    }); return () => m.remove()
  }, [])
  useEffect(() => {
    vehicles.forEach(v => {
      let o = mk.current[v.plate]
      if (!o) {
        const d = document.createElement('div'); d.style.cursor = 'pointer'
        d.innerHTML = '<svg width="16" height="16" viewBox="0 0 16 16"><path d="M8 1l5 13-5-3-5 3z" fill="#9fb3c8" stroke="#0a0d12" stroke-width="1"/></svg>'
        d.onclick = ev => { ev.stopPropagation(); cb.current.onSelectVehicle(v.plate) }
        o = mk.current[v.plate] = { d, m: new maplibregl.Marker({ element: d }).setLngLat(posOf(v)).addTo(map.current) }
      }
      o.m.setLngLat(posOf(v)); const sel = v.plate === selected?.plate, s = o.d.firstChild
      s.style.transform = `rotate(${headingOf(v)}deg)`; s.style.filter = sel ? 'drop-shadow(0 0 6px #22c3e6)' : ''
      s.querySelector('path').setAttribute('fill', sel ? '#22c3e6' : '#9fb3c8'); o.d.style.zIndex = sel ? 5 : 1
    })
    const m = map.current; if (!ready.current || !selected) return
    const v = vehicles.find(x => x.plate === selected.plate), p = posOf(v), pr = predict(v)
    m.getSource('obs').setData(fc([line([...v.history.map(h => [camById[h.cam].lng, camById[h.cam].lat]), p])]))
    const c = camById[v.to], hop = line([p, [c.lng, c.lat]], { w: 3, op: .9 })
    m.getSource('pred').setData(fc([hop, ...pr.map(r => line([[c.lng, c.lat], [camById[r.cam].lng, camById[r.cam].lat]], { w: 1 + r.probability * 5, op: .25 + r.probability * .75 }))]))
    labels.current.forEach(l => l.remove()); labels.current = pr.map(r => {
      const d = document.createElement('div'); d.textContent = Math.round(r.probability * 100) + '%'
      d.className = 'glass px-1.5 py-0.5 text-[11px] text-cy'; const b = camById[r.cam]; return new maplibregl.Marker({ element: d }).setLngLat([(c.lng + b.lng) / 2, (c.lat + b.lat) / 2]).addTo(m)
    })
  }, [vehicles, selected])
  useEffect(() => { if (selected) { const v = vehicles.find(x => x.plate === selected.plate); map.current?.flyTo({ center: posOf(v), zoom: 13.4 }) } }, [selected?.plate])
  return <div className="absolute inset-0"><div ref={el} style={{ width: "100%", height: "100%" }} /></div>
}
