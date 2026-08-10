#!/usr/bin/env python3
"""Generate SLSA-style Pocket Lab release provenance metadata and optionally sign blobs with Cosign.

No formal SLSA level is claimed. Signing is always explicit and never part of docs generation.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'contracts/generated/release-provenance.json'
SIGNATURES_OUT=ROOT/'contracts/generated/release-signatures.json'
SUPPLY=ROOT/'contracts/generated/supply-chain'
TOOL_ROOT=ROOT/'.pocketlab-dev/tools/documentation-security/bin'


def digest(path:Path)->str:
 h=hashlib.sha256();
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
 return h.hexdigest()


def stable(x:Any)->str: return json.dumps(x,sort_keys=True,indent=2,ensure_ascii=False)+'\n'

def git(*args:str)->str:
 return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()

def artifacts()->list[dict[str,Any]]:
 paths=[ROOT/'dist.zip',ROOT/'checksums.txt',ROOT/'pocketlab-lite-release.json',SUPPLY/'sbom-dev.cdx.json',SUPPLY/'sbom-release.cdx.json',SUPPLY/'sbom-runtime.cdx.json']
 return [{'path':str(p.relative_to(ROOT)),'sha256':digest(p),'bytes':p.stat().st_size} for p in paths if p.exists()]

def generate()->int:
 try: tag=git('describe','--tags','--exact-match','HEAD')
 except Exception: tag=None
 payload={
  'schema_version':'1.0.0',
  'predicate_type':'https://slsa.dev/provenance/v1',
  'formal_slsa_level':'not-claimed',
  'implementation_status':'implemented',
  'source':{'commit':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'exact_tag':tag},
  'builder':{'id':'pocket-lab-lite/wsl2-ci-explicit-release-workflow'},
  'build_type':'pocket-lab-lite/dist-zip-and-documentation-evidence',
  'subjects':artifacts(),
  'invocation':{'docs_generated_live_runtime':False,'runtime_promotion_implicit':False,'signing_implicit':False},
  'signing':{'workflow':'cosign sign-blob --yes --bundle <bundle> <artifact>','status':'unobserved-until-explicit-sign-command','keyless_preferred':True},
 }
 OUT.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix='.release-provenance.',dir=OUT.parent)
 try:
  with os.fdopen(fd,'w',encoding='utf-8') as fh:
   fh.write(stable(payload)); fh.flush(); os.fsync(fh.fileno())
  os.replace(tmp,OUT)
 finally:
  if os.path.exists(tmp): os.unlink(tmp)
 print(f'PASS generated SLSA-style provenance metadata: {OUT.relative_to(ROOT)}')
 return 0

def cosign_path()->str:
 local=TOOL_ROOT/'cosign'
 if local.exists(): return str(local)
 found=shutil.which('cosign')
 if not found: raise SystemExit('ERROR: cosign is missing; run task lite:docs:security-tools:setup')
 return found

def sign(path:Path,bundle:Path)->int:
 if not path.exists(): raise SystemExit(f'ERROR: artifact does not exist: {path}')
 bundle.parent.mkdir(parents=True,exist_ok=True)
 env={k:v for k,v in os.environ.items() if k not in {'COSIGN_PASSWORD'}}
 # Keyless/default Sigstore flow. No private key or credential is persisted by this script.
 subprocess.run([cosign_path(),'sign-blob','--yes','--bundle',str(bundle),str(path)],cwd=ROOT,env=env,check=True)
 print(f'PASS cosign bundle written outside tracked docs: {bundle}')
 return 0

def verify(path:Path,bundle:Path,identity:str,issuer:str)->int:
 if not path.exists(): raise SystemExit(f'ERROR: artifact does not exist: {path}')
 if not bundle.exists(): raise SystemExit(f'ERROR: Sigstore bundle does not exist: {bundle}')
 if not identity or not issuer: raise SystemExit('ERROR: certificate identity and OIDC issuer are required for keyless bundle verification')
 subprocess.run([cosign_path(),'verify-blob',str(path),'--bundle',str(bundle),'--certificate-identity',identity,'--certificate-oidc-issuer',issuer],cwd=ROOT,check=True)
 print(f'PASS verified Sigstore bundle for {path.name}')
 return 0



def release_signing_subjects()->list[Path]:
 paths=[ROOT/'dist.zip',ROOT/'pocketlab-lite-release.json',SUPPLY/'sbom-dev.cdx.json',SUPPLY/'sbom-release.cdx.json',SUPPLY/'sbom-runtime.cdx.json',OUT]
 return [p for p in paths if p.exists()]

def bundle_name(path:Path)->str:
 return path.name.replace('/', '_') + '.sigstore.json'

def sign_release_set(directory:Path)->int:
 subjects=release_signing_subjects()
 if not subjects: raise SystemExit('ERROR: no applicable release artifacts exist to sign')
 directory.mkdir(parents=True,exist_ok=True)
 rows=[]
 for subject in subjects:
  bundle=directory/bundle_name(subject)
  sign(subject,bundle)
  rows.append({'artifact':str(subject.relative_to(ROOT)),'sha256':digest(subject),'bundle':bundle.name,'bundle_sha256':digest(bundle),'verification_status':'signed-unverified'})
 manifest={'schema_version':'1.0.0','implementation_status':'implemented','canonical':False,'raw_secrets_included':False,'subjects':rows,'note':'Transient signing evidence. Verify with the expected keyless identity/issuer before explicit canonical promotion.'}
 (directory/'signing-manifest.json').write_text(stable(manifest),encoding='utf-8')
 print(f'PASS signed {len(rows)} applicable release artifacts; verification/promotion remains explicit')
 return 0

def verify_release_set(directory:Path,identity:str,issuer:str,promote:bool)->int:
 manifest_path=directory/'signing-manifest.json'
 if not manifest_path.exists(): raise SystemExit(f'ERROR: signing manifest is missing: {manifest_path}')
 manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
 verified=[]
 for row in manifest.get('subjects',[]):
  artifact=ROOT/str(row['artifact']); bundle=directory/str(row['bundle'])
  if digest(artifact)!=row.get('sha256') or digest(bundle)!=row.get('bundle_sha256'):
   raise SystemExit(f"ERROR: signing evidence digest mismatch for {row.get('artifact')}")
  verify(artifact,bundle,identity,issuer)
  verified.append({'artifact':row['artifact'],'sha256':row['sha256'],'bundle_sha256':row['bundle_sha256'],'status':'verified','certificate_identity_sha256':hashlib.sha256(identity.encode()).hexdigest(),'oidc_issuer':issuer})
 if promote:
  payload={'schema_version':'1.0.0','implementation_status':'implemented','evidence_status':'verified-keyless-signatures','raw_secrets_included':False,'formal_slsa_level':'not-claimed','source_commit':git('rev-parse','HEAD'),'release_tag':None,'subjects':verified}
  try: payload['release_tag']=git('describe','--tags','--exact-match','HEAD')
  except Exception: pass
  SIGNATURES_OUT.parent.mkdir(parents=True,exist_ok=True)
  fd,tmp=tempfile.mkstemp(prefix='.release-signatures.',dir=SIGNATURES_OUT.parent)
  try:
   with os.fdopen(fd,'w',encoding='utf-8') as fh:
    fh.write(stable(payload)); fh.flush(); os.fsync(fh.fileno())
   os.replace(tmp,SIGNATURES_OUT)
  finally:
   if os.path.exists(tmp): os.unlink(tmp)
  print(f'PASS promoted verified signature evidence: {SIGNATURES_OUT.relative_to(ROOT)}')
 else:
  print(f'PASS verified {len(verified)} release artifact signatures; canonical promotion not requested')
 return 0

def main()->int:
 ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='mode',required=True)
 sub.add_parser('generate')
 p=sub.add_parser('sign'); p.add_argument('--artifact',required=True); p.add_argument('--bundle',required=True)
 p=sub.add_parser('verify'); p.add_argument('--artifact',required=True); p.add_argument('--bundle',required=True); p.add_argument('--identity',required=True); p.add_argument('--issuer',required=True)
 p=sub.add_parser('sign-release-set'); p.add_argument('--directory',default=str(ROOT/'.pocketlab-dev/release-signatures'))
 p=sub.add_parser('verify-release-set'); p.add_argument('--directory',default=str(ROOT/'.pocketlab-dev/release-signatures')); p.add_argument('--identity',required=True); p.add_argument('--issuer',required=True); p.add_argument('--promote',action='store_true')
 a=ap.parse_args()
 if a.mode=='generate': return generate()
 if a.mode=='sign': return sign(Path(a.artifact).resolve(),Path(a.bundle).resolve())
 if a.mode=='verify': return verify(Path(a.artifact).resolve(),Path(a.bundle).resolve(),a.identity,a.issuer)
 if a.mode=='sign-release-set': return sign_release_set(Path(a.directory).resolve())
 return verify_release_set(Path(a.directory).resolve(),a.identity,a.issuer,a.promote)
if __name__=='__main__': raise SystemExit(main())
