import {motion} from 'framer-motion'
import {predict} from '../hooks/useSimulation'
const Row=([k,v])=><div key={k}><div className="text-[11px] text-slate-500">{k}</div><div className="text-sm">{v}</div></div>
export default function VehiclePanel({v,onClose}){
 const pr=predict(v),h=v.plate.charCodeAt(4)
 const why=[['Plate match',.98],['Colour match',.91],['Company match',.96],['Travel time',.87],['Direction',.95]].map(([k,x])=>[k,Math.min(.99,x-(v.confidence<.95?(h%7)/100:0))])
 return <motion.aside initial={{x:40,opacity:0}} animate={{x:0,opacity:1}} className="glass p-4 overflow-y-auto h-full space-y-5">
  <div className="flex justify-between items-start"><div><div className="text-[11px] text-slate-500">Vehicle</div><div className="text-xl font-semibold tracking-wide">{v.plate}</div>
   <div className="text-xs text-ok">{(v.confidence*100).toFixed(1)}% match confidence</div></div><button onClick={onClose} className="text-slate-500 text-lg">×</button></div>
  <div className="grid grid-cols-2 gap-3">{[['Vehicle',v.company+' '+v.model],['Colour',v.color],['Type',v.type],['Current camera',v.from],['First seen',v.history[0].time],['Sightings',v.history.length]].map(Row)}</div>
  <section><div className="text-xs text-slate-400 mb-2">Likely next locations</div>
   {pr.map((r,i)=><div key={r.cam} className="flex items-center justify-between py-1.5 border-b border-line" style={{opacity:1-i*.2}}>
    <div><span className={i?'':'text-cy font-medium'}>{r.cam}</span><div className="text-[11px] text-slate-500">ETA {r.eta}</div></div>
    <div className={i?'text-slate-300':'text-cy text-lg font-semibold'}>{Math.round(r.probability*100)}%</div></div>)}
   <p className="text-[11px] text-slate-500 mt-2">Prediction based on road topology, historical travel time and vehicle evidence.</p></section>
  <section><div className="text-xs text-slate-400 mb-2">Why this vehicle?</div>
   {why.map(([k,x])=><div key={k} className="mb-2"><div className="flex justify-between text-[11px]"><span>{k}</span><span>{Math.round(x*100)}%</span></div>
    <div className="h-1.5 bg-line rounded"><div className="h-full rounded bg-cy" style={{width:x*100+'%'}}/></div></div>)}
   <div className="flex justify-between text-sm pt-1"><span>Overall match</span><span className="text-ok font-semibold">{(v.confidence*100).toFixed(1)}%</span></div></section>
  <section><div className="text-xs text-slate-400 mb-2">Trajectory timeline</div>
   {[...v.history].reverse().map((s,i)=><div key={i} className="flex gap-3 text-sm py-1"><span className="text-slate-500 w-20">{s.time}</span><span className={i?'':'text-cy'}>{s.cam}</span></div>)}</section>
 </motion.aside>}
