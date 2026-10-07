const B=import.meta.env.VITE_API_URL
export const getVehicles=()=>B?fetch(B+'/vehicles').then(r=>r.json()):import('../data/mock.js').then(m=>m.vehicles)
export const getPrediction=id=>B?fetch(`${B}/predict/${id}`).then(r=>r.json()):null
