import http from 'k6/http';
import { check, sleep } from 'k6';

export const options={vus:2,duration:'8s',insecureSkipTLSVerify:true,thresholds:{http_req_failed:['rate<0.20'],http_req_duration:['p(95)<2000']}};
const BASE='https://127.0.0.1:18443';
const HOST=__ENV.POCKETLAB_FIXED_CADDY_HOST;
if(!HOST) throw new Error('fixed Caddy identity unavailable');
export default function(){
  const p={headers:{Host:HOST,Accept:'application/json'},timeout:'3s'};
  const h=http.get(BASE+'/health',p); check(h,{'health remains available':r=>r.status===200});
  const d=http.post(BASE+'/api/lite/harness/security-assurance/runs',JSON.stringify({suite_id:'smoke'}),{...p,headers:{...p.headers,'Content-Type':'application/json','X-Pocket-Lab-Harness-Session':'forged'}});
  check(d,{'forged assurance remains denied':r=>r.status>=400}); sleep(.25);
}
