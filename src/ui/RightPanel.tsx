import type { Engine } from '../sim/engine';
import { formatPlate } from '../sim/plates';
import type { Mode, Trace } from '../track/link';

const fmtT = (t: number) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;

export type RightPanelProps = {
  engine: Engine;
  carId: string | null;
  trace: Trace | null;
  mode: Mode;
  setMode: (m: Mode) => void;
  reveal: boolean;
  setReveal: (b: boolean) => void;
  showReach: boolean;
  setShowReach: (b: boolean) => void;
  search: string;
  setSearch: (s: string) => void;
  onSearch: () => void;
  onDeselect: () => void;
  trueRank: (segIdx: number) => number | null;
};

export function RightPanel(p: RightPanelProps) {
  const { engine, carId, trace } = p;
  const cs = carId ? engine.carById.get(carId) : undefined;
  const g = engine.graph;

  return (
    <div className="panel right">
      <h3>Track a car</h3>
      <div className="row">
        <input type="text" placeholder="plate, e.g. KA01AB1234" value={p.search} onChange={e => p.setSearch(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && p.onSearch()} style={{ flex: 1 }} />
        <button onClick={p.onSearch}>Find</button>
      </div>
      <div className="row" style={{ marginTop: 6 }}>
        <button className={p.mode === 'ours' ? 'on' : ''} onClick={() => p.setMode('ours')}>Our method</button>
        <button className={p.mode === 'naive' ? 'on' : ''} onClick={() => p.setMode('naive')}>Naive (exact plate)</button>
      </div>
      {!cs && <p className="dim">Click a car on the map (or search a plate) to track it.</p>}
      {cs && (
        <>
          <div className="card">
            <div className="mono" style={{ fontSize: 16 }}>{formatPlate(cs.car.plate)}</div>
            <div>{cs.car.type} · {cs.car.colour}
              {cs.car.lookalikeOf && <span className="chip warn" style={{ marginLeft: 6 }}>has a look-alike twin</span>}</div>
            <div className="row" style={{ marginTop: 6 }}>
              <button className={p.reveal ? 'primary' : ''} onClick={() => p.setReveal(!p.reveal)}>{p.reveal ? 'Hide true route' : 'Reveal true route'}</button>
              <button className={p.showReach ? 'on' : ''} onClick={() => p.setShowReach(!p.showReach)}>Where now?</button>
              <button onClick={p.onDeselect}>Clear</button>
            </div>
          </div>

          {trace && !trace.first && <p className="warn">No sighting of this plate yet — add cameras or let time run.</p>}
          {trace && trace.first && (
            <>
              <h3>Sighting timeline ({trace.linked.length} linked)</h3>
              <table>
                <thead><tr><th></th><th>t</th><th>cam</th><th>read</th><th>conf</th></tr></thead>
                <tbody>
                  {trace.decisions.map(d => {
                    const s = d.sighting;
                    const actual = p.reveal ? (s.trueCarId === carId ? 'this car' : `actually ${s.trueCarId}`) : null;
                    return (
                      <tr key={s.id}>
                        <td className={d.status === 'linked' ? 'ok' : 'no'}>{d.status === 'linked' ? '✓' : '✗'}</td>
                        <td>{fmtT(s.t)}</td><td>{s.nodeId}</td>
                        <td className="mono">{s.plateRead ?? '—'}</td><td>{s.plateConf.toFixed(2)}</td>
                        <td className="dim" style={{ fontSize: 11 }}>{d.reason}{actual && <span className={s.trueCarId === carId ? 'ok' : 'no'}> · {actual}</span>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              <h3>Possible routes between sightings</h3>
              {trace.segments.length === 0 && <p className="dim">Need at least two linked sightings.</p>}
              {trace.segments.map((sg, i) => {
                const inf = sg.inference;
                const rank = p.reveal ? p.trueRank(i) : null;
                return (
                  <div className="card" key={sg.from.id + sg.to.id}>
                    <b>{sg.from.nodeId} → {sg.to.nodeId}</b> <span className="dim">({Math.round(sg.to.t - sg.from.t)} s)</span>
                    <div>
                      <span className="chip">{inf.rawCount} feasible</span>
                      <span className="chip">≈ {inf.effective.toFixed(1)} effective routes</span>
                      {p.reveal && <span className={'chip ' + (rank === 1 ? 'ok' : 'no')}>true route rank: {rank ?? 'not found'}</span>}
                    </div>
                    {sg.from.nodeId === sg.to.nodeId && <div className="dim">Returned to the same camera (route unknowable).</div>}
                    {inf.hyps.slice(0, 5).map((h, k) => (
                      <div key={k} style={{ marginTop: 3 }}>
                        <span className="mono">#{k + 1}</span> {(h.prob * 100).toFixed(0)}% · {Math.round(h.travelTimeS)} s · {h.edgeIds.length} roads
                        <div className="bar" style={{ width: `${Math.max(2, h.prob * 100)}%`, opacity: k === 0 ? 1 : 0.55 }} />
                      </div>
                    ))}
                    {inf.hyps.length > 5 && <div className="dim">+{inf.hyps.length - 5} more routes</div>}
                  </div>
                );
              })}
            </>
          )}
        </>
      )}
      <div className="dim" style={{ marginTop: 8, fontSize: 11 }}>
        Legend: amber = route hypotheses (opacity ∝ probability), cyan haze = where it could be now, green ring = linked sighting,
        red dot = rejected look-alike, green dashed = true route. Graph: {g.N} junctions.
      </div>
    </div>
  );
}
