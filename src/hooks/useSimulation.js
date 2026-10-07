import {useEffect,useRef,useState,useCallback} from 'react'
import {vehicles as seed,cameras,camById,adj} from '../data/mock'
import {connectEvents} from '../services/websocket'
const pick=a=>a[Math.floor(Math.random()*a.length)],ids=cameras.map(c=>c.id)
const clock=()=>new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit'})
const init=()=>seed.map((v,i)=>{if(i===0)return{...v,from:'C07',to:'C08',t:.4,history:[{cam:'C01',time:'10:31 AM'},{cam:'C02',time:'10:36 AM'},{cam:'C07',time:'10:44 AM'}]}
 const from=pick(ids);return{...v,from,to:pick(adj[from]),t:Math.random(),history:[{cam:from,time:clock()}]}})
export const posOf=v=>{const a=camById[v.from],b=camById[v.to];return[a.lng+(b.lng-a.lng)*v.t,a.lat+(b.lat-a.lat)*v.t]}
export const headingOf=v=>{const a=camById[v.from],b=camById[v.to];return Math.atan2(b.lng-a.lng,b.lat-a.lat)*180/Math.PI}
export function predict(v){const opts=adj[v.to].filter(c=>c!==v.from).sort().slice(0,3),w=[.62,.27,.11].slice(0,opts.length),s=w.reduce((x,y)=>x+y)
 const rem=(1-v.t)*3+3;return opts.map((cam,i)=>({cam,from:v.to,probability:w[i]/s,eta:`${Math.round(rem+i)}–${Math.round(rem+i+3)} min`}))}
export function useSimulation(){
 const [vs,setVs]=useState(init),[events,setEvents]=useState([]),[running,setRunning]=useState(true),[speed,setSpeed]=useState(1)
 const ref=useRef(vs);const push=useCallback(e=>setEvents(p=>[{id:Math.random(),time:clock(),...e},...p].slice(0,30)),[])
 useEffect(()=>connectEvents(push),[push])
 useEffect(()=>{if(!running)return;const h=setInterval(()=>{const out=[]
  ref.current=ref.current.map(v=>{let n={...v,t:v.t+.004*speed};if(n.t>=1){const o=adj[n.to].filter(c=>c!==n.from)
   n={...n,from:n.to,to:pick(o.length?o:adj[n.to]),t:0,history:[...n.history,{cam:n.to,time:clock()}].slice(-12)}
   out.push({cam:n.from,text:Math.random()<.2?'Plate matched':'Vehicle detected',plate:n.plate})}return n})
  setVs(ref.current);if(out.length)setEvents(p=>[...out.map(e=>({id:Math.random(),time:clock(),...e})),...p].slice(0,30))},100);return()=>clearInterval(h)},[running,speed])
 return{vehicles:vs,events,running,speed,setSpeed,toggle:()=>setRunning(r=>!r),
  reset:()=>{ref.current=init();setVs(ref.current);setEvents([])}}
}
