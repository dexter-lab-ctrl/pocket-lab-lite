# Android / Termux Quick Start

Pocket Lab Lite is intended to run on lower-power Android/Termux and edge devices while keeping the same control-plane boundary as full Pocket Lab.

## Clone the repository

```bash
pkg update
pkg install git
git clone https://github.com/dexter-lab-ctrl/pocket-lab-lite.git
cd pocket-lab-lite
```

## Run the lite bootstrap

```bash
cd pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched
bash scripts/bootstrap.sh --profile lite
```

The lite profile should start only the core services needed for the lightweight control plane.

## Open the UI

Open the local dashboard URL shown by the bootstrap output.

Expected local endpoints after the lite backend is implemented:

```bash
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/ready
curl -s http://127.0.0.1:8080/api/lite/status
```

Expected result:

```text
health = healthy
ready = ready
lite status = overall healthy or degraded with a clear reason
```
