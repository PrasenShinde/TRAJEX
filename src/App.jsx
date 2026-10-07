import {useEffect,useState} from 'react'
import {AnimatePresence,motion} from 'framer-motion'
import {LayoutDashboard,Video,Search,Route,Bell,Camera,BarChart3,Network,Settings,FileText,Radar,Play,Pause,RotateCcw,PanelLeft} from 'lucide-react'
import MapView from './components/MapView'
import VehiclePanel from './components/VehiclePanel'
import {useSimulation} from './hooks/useSimulation'
import {cameras,camById} from './data/mock'
const nav=[[LayoutDashboard,'Dashboard'],[Video,'Live Monitoring'],[Search,'Vehicle Search'],[Route,'Trajectory'],[Bell,'Alerts'],[Camera,'CCTV Cameras'],[BarChart3,'Traffic Analytics'],0,[Radar,'Simulation'],[Network,'Road Network'],[Camera,'Camera Simulator'],0,[FileText,'Reports'],[Settings,'Settings']]
const Ic=({i:I})=><I size={16}/>
function useCount(n,ms=900){const[v,s]=useState(0);useEffect(()=>{const t0=performance.now();let r;const f=t=>{const p=Math.min(1,(t-t0)/ms);s(Math.round(n*p));p<1&&(r=requestAnimationFrame(f))};r=requestAnimationFrame(f);return()=>cancelAnimationFrame(r)},[n]);return v}
const KPI=({k,n,fmt=x=>x})=>{const v=useCount(n);return <div className="glass px-3 py-2 min-w-[110px]"><div className="text-[11px] text-slate-400">{k}</div><div className="text-lg font-semibold">{fmt(v)}</div></div>}
export default function App(){
 const sim=useSimulation(),[sel,setSel]=useState('MH30AB1234'),[cam,setCam]=useState(null),[col,setCol]=useState(false),[now,setNow]=useState(new Date())
 useEffect(()=>{const h=setInterval(()=>setNow(new Date()),1000);return()=>clearInterval(h)},[])
 const v=sim.vehicles.find(x=>x.plate===sel),c=cam&&camById[cam]
 return <div className="h-full flex flex-col">
  <header className="h-12 shrink-0 flex items-center gap-4 px-4 border-b border-line bg-panel">
   <div className="flex items-center gap-2"><Radar className="text-cy" size={20}/><div><div className="font-semibold leading-none tracking-wide">TRAJEX</div><div className="text-[10px] text-slate-500">City Vehicle Intelligence</div></div></div>
   <div className="flex-1 max-w-md mx-auto relative"><Search size={14} className="absolute left-3 top-2.5 text-slate-500"/>
    <input placeholder="Search plate, vehicle, camera..." onKeyDown={e=>{const p=sim.vehicles.find(x=>x.plate===e.target.value.toUpperCase().trim());if(e.key==='Enter'&&p)setSel(p.plate)}}
     className="w-full h-8 rounded-lg bg-bg border border-line pl-8 text-sm outline-none focus:border-cy"/></div>
   <span className="hidden md:block text-[10px] px-2 py-0.5 rounded bg-warn/15 text-warn">SIMULATION MODE</span>
   <span className="flex items-center gap-1.5 text-xs text-ok"><span className="size-2 rounded-full bg-ok animate-pulse"/>LIVE</span>
   <span className="hidden sm:block text-xs text-slate-400 tabular-nums">{now.toLocaleTimeString('en-IN')}</span><Bell size={16} className="text-slate-400"/>
   <div className="size-7 rounded-full bg-line grid place-items-center text-xs">OP</div></header>
  <div className="flex-1 flex min-h-0">
   <aside className={`${col?'w-14':'w-52 max-md:w-14'} shrink-0 border-r border-line bg-panel p-2 flex flex-col transition-all`}>
    <button onClick={()=>setCol(!col)} className="p-2 text-slate-500 self-start"><PanelLeft size={16}/></button>
    {nav.map((n,i)=>n?<button key={i} className={`flex items-center gap-3 px-2.5 py-2 rounded-lg text-sm ${i===0?'bg-cy/10 text-cy':'text-slate-400 hover:bg-line/50'}`}><Ic i={n[0]}/>{!col&&<span className="max-md:hidden">{n[1]}</span>}</button>:<div key={i} className="h-px bg-line my-2"/>)}
    <div className={`mt-auto text-[11px] space-y-1 ${col?'hidden':'max-md:hidden'}`}><div className="text-slate-500">System status</div>
     <div className="text-ok">● 18 cameras online</div><div className="text-warn">● 2 cameras degraded</div><div className="text-bad">● 0 cameras offline</div></div></aside>
   <main className="flex-1 flex flex-col min-w-0">
    <div className="flex-1 flex min-h-0">
     <div className="flex-1 relative">
      <MapView vehicles={sim.vehicles} selected={v} onSelectVehicle={setSel} onSelectCamera={setCam}/>
      <div className="absolute top-3 left-3 right-3 flex gap-2 flex-wrap pointer-events-none">
       <KPI k="Vehicles detected" n={1284} fmt={x=>x.toLocaleString()}/><KPI k="Active vehicles" n={347}/><KPI k="Cameras online" n={18} fmt={x=>x+' / 20'}/><KPI k="Active alerts" n={7} fmt={x=>String(x).padStart(2,'0')}/><KPI k="Avg travel time" n={522} fmt={x=>`${Math.floor(x/60)}m ${String(x%60).padStart(2,'0')}s`}/></div>
      <div className="absolute bottom-3 left-3 glass px-3 py-2 text-[11px] text-slate-300 space-y-1">
       <div className="flex items-center gap-2"><span className="w-6 border-t-2 border-cy"/>Observed</div><div className="flex items-center gap-2"><span className="w-6 border-t-2 border-dashed border-cy"/>Predicted</div></div>
     </div>
     <div className="max-lg:fixed max-lg:inset-x-0 max-lg:bottom-0 max-lg:h-[55vh] max-lg:z-20 lg:w-[340px] p-2 lg:pl-0"><AnimatePresence>{v&&<VehiclePanel key={v.plate} v={v} onClose={()=>setSel(null)}/>}</AnimatePresence></div>
    </div>
    <footer className="h-40 shrink-0 border-t border-line bg-panel flex">
     <div className="flex-1 overflow-hidden p-3"><div className="text-xs text-slate-400 mb-1">Live events</div>
      <div className="space-y-0.5 h-28 overflow-hidden"><AnimatePresence initial={false}>{sim.events.slice(0,6).map(e=><motion.div key={e.id} layout initial={{opacity:0,y:-10}} animate={{opacity:1,y:0}}
       className="flex gap-3 text-xs"><span className="text-slate-500 tabular-nums">{e.time}</span><span className="text-cy w-8">{e.cam}</span><span className="w-32 text-slate-300">{e.text}</span><button onClick={()=>setSel(e.plate)} className="hover:text-cy">{e.plate}</button></motion.div>)}</AnimatePresence></div></div>
     <div className="w-64 border-l border-line p-3 text-xs space-y-2 max-sm:hidden"><div className="text-slate-400">Simulation</div>
      <div className="flex gap-2"><button onClick={sim.toggle} className="glass p-1.5">{sim.running?<Pause size={14}/>:<Play size={14}/>}</button><button onClick={sim.reset} className="glass p-1.5"><RotateCcw size={14}/></button>
       {[1,5,10].map(s=><button key={s} onClick={()=>sim.setSpeed(s)} className={`glass px-2 ${sim.speed===s?'text-cy border-cy':''}`}>{s}x</button>)}</div>
      {c?<div><div className="text-cy">{c.id} · {c.name}</div><div className="text-slate-400">{c.status} · {c.fps} FPS · {c.perMin}/min · {c.rate}%</div></div>:<div className="text-slate-500">Select a camera on the map for stats.</div>}</div>
    </footer>
   </main></div></div>}
