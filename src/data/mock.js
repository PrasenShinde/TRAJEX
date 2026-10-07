// Swap these exports for REST calls in services/api.js later.
const names=['Main Road North','Market Junction','Station Road','Ring Road East','Civil Lines']
export const cameras=Array.from({length:20},(_,i)=>{const c=i%5,r=Math.floor(i/5)
 return{id:'C'+String(i+1).padStart(2,'0'),name:names[c]+' '+(r+1),lng:77+c*.012+((i*7)%5)*.001,lat:20.7+r*.01+((i*3)%4)*.001,
 status:i===2||i===10?'degraded':'online',fps:i===2||i===10?15:28,perMin:30+(i*13)%40,rate:i===2||i===10?82.1:93+(i%5)}})
export const camById=Object.fromEntries(cameras.map(c=>[c.id,c]))
export const edges=[];export const adj={}
cameras.forEach(c=>adj[c.id]=[])
cameras.forEach((c,i)=>{[[i%5<4,i+1],[i<15,i+5]].forEach(([ok,j])=>{if(ok){const d=cameras[j].id;adj[c.id].push(d);adj[d].push(c.id)
 edges.push({a:c.id,b:d,level:(i*7)%5===0?2:i%3===0?1:0})}})})
const mk=[['Hyundai','Creta'],['Maruti','Swift'],['Tata','Nexon'],['Honda','City'],['Mahindra','XUV700'],['Kia','Seltos']]
const col=['White','Silver','Black','Red','Blue','Grey'],types=['Car','Car','Car','SUV','Truck','Bike']
export const vehicles=Array.from({length:104},(_,i)=>{const [company,model]=mk[i%6]
 return i===0?{plate:'MH30AB1234',company:'Hyundai',model:'Creta',color:'White',type:'Car',confidence:.968}
 :{plate:`MH${10+(i*7)%40}${'ABCDXYZ'[i%7]}${'CDEFGHK'[(i*3)%7]}${1000+(i*397)%9000}`,company,model,color:col[(i*5)%6],type:types[i%6],confidence:.82+((i*37)%17)/100}})
