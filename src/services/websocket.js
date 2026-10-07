export function connectEvents(onEvent,url=import.meta.env.VITE_WS_URL){
 if(!url)return()=>{};const ws=new WebSocket(url);ws.onmessage=e=>onEvent(JSON.parse(e.data));return()=>ws.close()}
