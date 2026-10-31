import type { Batch, EvalResult } from '../track/eval';

export type LiveMetrics = {
  cameras: number; junctions: number;
  avgRoutes: number | null; segCount: number;
  routeAccuracy: number | null; meanRank: number | null; // need reveal
  linkOurs: { precision: number; recall: number; n: number } | null;
  linkNaive: { precision: number; recall: number; n: number } | null;
};
export type BatchState = { running: boolean; progress: number; label: string; result: (Batch & { currentRandom: EvalResult; currentSmart: EvalResult }) | null };

const pct = (x: number | null) => (x === null ? '—' : `${Math.round(x * 100)}%`);

function Chart({ data, current }: { data: Batch['chart']; current: number }) {
  const W = 360, H = 118, L = 34, B = 20, T = 8, R = 10;
  const xs = data.map(d => d.cameras);
  const maxY = Math.max(1, ...data.flatMap(d => [d.random, d.smart]));
  const x = (v: number) => L + ((v - Math.min(...xs)) / (Math.max(...xs) - Math.min(...xs) || 1)) * (W - L - R);
  const y = (v: number) => T + (1 - v / maxY) * (H - T - B);
  const line = (k: 'random' | 'smart') => data.map((d, i) => `${i ? 'L' : 'M'}${x(d.cameras).toFixed(1)},${y(d[k]).toFixed(1)}`).join(' ');
  return (
    <svg width={W} height={H} role="img" aria-label="Average possible routes versus number of cameras, random versus smart placement">
      <line x1={L} y1={H - B} x2={W - R} y2={H - B} stroke="#2a313c" />
      <line x1={L} y1={T} x2={L} y2={H - B} stroke="#2a313c" />
      {[0, 0.5, 1].map(f => <text key={f} x={L - 4} y={y(maxY * f) + 3} fill="#8b95a5" fontSize="9" textAnchor="end">{(maxY * f).toFixed(0)}</text>)}
      {data.map(d => <text key={d.cameras} x={x(d.cameras)} y={H - 6} fill="#8b95a5" fontSize="9" textAnchor="middle">{d.cameras}</text>)}
      <path d={line('random')} stroke="#f87171" fill="none" strokeWidth="2" />
      <path d={line('smart')} stroke="#4ade80" fill="none" strokeWidth="2" />
      {data.map(d => <circle key={'r' + d.cameras} cx={x(d.cameras)} cy={y(d.random)} r="3" fill="#f87171" />)}
      {data.map(d => <circle key={'s' + d.cameras} cx={x(d.cameras)} cy={y(d.smart)} r="3" fill="#4ade80" />)}
      <text x={W - R} y={T + 8} fill="#f87171" fontSize="10" textAnchor="end">random</text>
      <text x={W - R} y={T + 20} fill="#4ade80" fontSize="10" textAnchor="end">smart</text>
      <text x={L + 4} y={T + 8} fill="#8b95a5" fontSize="9">avg possible routes ↓ vs cameras →</text>
      {current >= Math.min(...xs) && current <= Math.max(...xs) && <line x1={x(current)} y1={T} x2={x(current)} y2={H - B} stroke="#4cc9f0" strokeDasharray="3 3" />}
    </svg>
  );
}

export function BottomStrip(p: { live: LiveMetrics; batch: BatchState; onRun: () => void; nTrips: number }) {
  const { live, batch } = p;
  const r = batch.result;
  return (
    <div className="panel bottom">
      <div className="metric">
        <h3>Live</h3>
        <div className="dim">Cameras</div><div className="big">{live.cameras} <span className="dim" style={{ fontSize: 12 }}>({Math.round((100 * live.cameras) / live.junctions)}% of junctions)</span></div>
        <div className="dim">Avg possible routes{live.segCount ? ` (last ${live.segCount} seg.)` : ''}</div>
        <div className="big">{live.avgRoutes === null ? '—' : live.avgRoutes.toFixed(1)}</div>
      </div>
      <div className="metric">
        <h3>Tracked car vs truth <span className="dim" style={{ textTransform: 'none' }}>(after Reveal)</span></h3>
        <div>Route accuracy: <b>{pct(live.routeAccuracy)}</b></div>
        <div>True route rank: <b>{live.meanRank === null ? '—' : live.meanRank.toFixed(1)}</b> <span className="dim">(1 = best)</span></div>
        <div>Link accuracy ours: <b>{live.linkOurs ? `${pct(live.linkOurs.precision)} (recall ${pct(live.linkOurs.recall)})` : '—'}</b></div>
        <div>Link accuracy naive: <b>{live.linkNaive ? `${pct(live.linkNaive.precision)} (recall ${pct(live.linkNaive.recall)})` : '—'}</b></div>
      </div>
      <div style={{ minWidth: 330 }}>
        <h3>Batch evaluation ({p.nTrips} random trips)</h3>
        <button className="primary" disabled={batch.running} onClick={p.onRun}>{batch.running ? `Running… ${Math.round(batch.progress * 100)}% ${batch.label}` : 'Run batch evaluation'}</button>
        {r && (
          <table style={{ marginTop: 4 }}>
            <thead><tr><th>placement ({r.current.cameras} cams)</th><th>avg routes</th><th>route acc.</th><th>true rank</th><th>top-1</th></tr></thead>
            <tbody>
              {([['current', r.current], ['random', r.currentRandom], ['smart', r.currentSmart]] as [string, EvalResult][]).map(([n, e]) => (
                <tr key={n}><td>{n}</td><td>{e.avgRoutes.toFixed(1)}</td><td>{pct(e.routeAccuracy)}</td><td>{e.meanRank ? e.meanRank.toFixed(1) : '—'}</td><td>{Math.round(e.top1Pct)}%</td></tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <div>{r ? <Chart data={r.chart} current={r.current.cameras} /> : <span className="dim">Run the batch evaluation to see avg possible routes vs number of cameras (random vs smart).</span>}</div>
    </div>
  );
}
