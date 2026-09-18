#!/usr/bin/env python3
"""Fixed DEV-PC runtime security probes; no caller-selected network/command inputs."""
from __future__ import annotations
import argparse, ipaddress, json, os, shutil, signal, socket, subprocess, time, urllib.error, urllib.request
API_BASE="http://127.0.0.1:18080"; NATS_URL="nats://127.0.0.1:14222"
ALLOWED_PORTS={14222,18080,18181,18222,18443}; TAILNET_EXPECTED={443,4222}; TAILNET_FORBIDDEN={8080,8181,8222}
def emit(status="PASS", findings=None, **extra):
    print(json.dumps({"status":status,"security_findings":findings or [],"sanitized":True,**extra},sort_keys=True))
def tool(name):
    value=shutil.which(name)
    if not value: raise RuntimeError("qualified_executable_not_found")
    return value
def run(argv,timeout=8):
    started=time.monotonic()
    try:
        p=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,shell=False,start_new_session=True,env=os.environ.copy())
        return p.returncode,p.stdout[:65536].decode("utf-8","replace"),p.stderr[:65536].decode("utf-8","replace"),int((time.monotonic()-started)*1000)
    except subprocess.TimeoutExpired:
        return 124,"","",int((time.monotonic()-started)*1000)
def fixed_get(path):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(urllib.request.Request(API_BASE+path,headers={"Accept":"application/json","Cache-Control":"no-cache"}),timeout=3) as r:
        return int(r.status),r.read(65536)
def tailnet_ip():
    try:
        status,raw=fixed_get("/api/lite/remote-access/readiness"); value=json.loads(raw.decode()) if status==200 else {}
    except Exception:
        return None
    values=[]
    def walk(v):
        if isinstance(v,dict):
            for x in v.values(): walk(x)
        elif isinstance(v,list):
            for x in v: walk(x)
        elif isinstance(v,str): values.append(v.strip())
    walk(value); network=ipaddress.ip_network("100.64.0.0/10")
    for raw in values:
        try: ip=ipaddress.ip_address(raw)
        except ValueError: continue
        if ip.version==4 and ip in network: return str(ip)
    return None
def websocket():
    code,out,_,duration=run([tool("websocat"),"-1","-t","ws://127.0.0.1:18080/ws/events"],4)
    accepted=bool(out.strip()) or code==0
    findings=[{"id":"unauthenticated-websocket-events","severity":"high","attack_paths":["AP-01","AP-09"],"summary":"Unauthenticated fixed WebSocket probe received or established event-stream access."}] if accepted else []
    emit("FAIL" if findings else "PASS",findings,connection_accepted=accepted,duration_ms=duration)
def mitmproxy():
    binary=tool("mitmdump")
    argv=[binary,"--listen-host","127.0.0.1","--listen-port","18081","--mode","reverse:http://127.0.0.1:18080","--set","block_global=false","--set","flow_detail=0","-q"]
    p=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,shell=False,start_new_session=True,env=os.environ.copy())
    try:
        time.sleep(.6); opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(urllib.request.Request("http://127.0.0.1:18081/health",headers={"Accept":"application/json"}),timeout=3) as r: health=int(r.status)==200
        req=urllib.request.Request("http://127.0.0.1:18081/api/lite/harness/security-assurance/runs",data=b'{"suite_id":"smoke"}',method="POST",headers={"Content-Type":"application/json","X-Pocket-Lab-Harness-Session":"forged","X-Forwarded-For":"127.0.0.1"})
        try:
            with opener.open(req,timeout=3) as r: rejected=int(r.status)>=400
        except urllib.error.HTTPError as e: rejected=int(e.code)>=400
        findings=[] if rejected else [{"id":"proxy-forged-authority-accepted","severity":"critical","attack_paths":["AP-01","AP-09"],"summary":"Fixed forged proxy authority request was not rejected."}]
        emit("FAIL" if findings else "PASS",findings,health_ok=health,forged_request_rejected=rejected)
    finally:
        try: os.killpg(p.pid,signal.SIGTERM)
        except OSError: pass
        try: p.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try: os.killpg(p.pid,signal.SIGKILL)
            except OSError: pass
def tshark():
    argv=[tool("tshark"),"-i","lo","-a","duration:3","-f","tcp port 18080 or tcp port 18443 or tcp port 14222 or tcp port 18181 or tcp port 18222","-T","fields","-e","tcp.dstport"]
    p=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=False,start_new_session=True,env=os.environ.copy()); time.sleep(.5)
    try: fixed_get("/health")
    except Exception: pass
    out,err=p.communicate(timeout=5)
    if p.returncode not in (0, None):
        emit("PARTIAL",failure_code="packet_observer_unavailable",payload_persisted=False); return
    ports=sorted({int(v) for v in out.decode("utf-8","replace").split() if v.isdigit() and int(v) in ALLOWED_PORTS})
    emit("PASS",observed_fixed_ports=ports,payload_persisted=False)
def nats():
    code,_,_,duration=run([tool("nats"),"--server",NATS_URL,"server","ping","--count","1"],6)
    emit("PASS" if code==0 else "PARTIAL",reachable=code==0,duration_ms=duration,failure_code=None if code==0 else "fixed_nats_observation_unavailable")
def tailnet():
    ip=tailnet_ip()
    if not ip:
        emit("BLOCKED",failure_code="remote_access_not_ready"); return
    observed={}
    for port in sorted(TAILNET_EXPECTED|TAILNET_FORBIDDEN):
        try:
            with socket.create_connection((ip,port),timeout=.8): observed[port]=True
        except OSError: observed[port]=False
    httpx=tool("httpx")
    code,out,_,_=run([httpx,"-u",f"http://{ip}:8080/health","-silent","-status-code","-no-color","-timeout","3","-retries","0"],6)
    direct_api=bool(out.strip())
    observed[8080]=observed.get(8080,False) or direct_api
    bad=[port for port in TAILNET_FORBIDDEN if observed.get(port)]
    missing=[port for port in TAILNET_EXPECTED if not observed.get(port)]
    findings=[]
    if bad:
        findings.append({"id":"unexpected-tailnet-service-exposure","severity":"high","attack_paths":["AP-07"],"summary":"An internal-only Pocket Lab service was reachable on the private-network address."})
    if missing:
        findings.append({"id":"expected-tailnet-service-unavailable","severity":"medium","attack_paths":["AP-07"],"summary":"A registered private-network service was unavailable while remote access reported ready."})
    emit("FAIL" if bad else "PARTIAL" if missing else "PASS",findings,remote_access_ready=True,
         expected_service_reachability={str(port):observed.get(port,False) for port in sorted(TAILNET_EXPECTED)},
         internal_only_exposed_count=len(bad),direct_api_http_observed=direct_api)
def main():
    p=argparse.ArgumentParser(); p.add_argument("mode",choices=("websocket","mitmproxy","tshark","nats","tailnet")); mode=p.parse_args().mode
    {"websocket":websocket,"mitmproxy":mitmproxy,"tshark":tshark,"nats":nats,"tailnet":tailnet}[mode]()
if __name__=="__main__": main()
