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

## Android boot recovery and native Termux interpreters

Pocket Lab Lite keeps the external runtime guardian outside PM2 so it can
recover PM2 when the PM2 daemon is stopped. The repository-owned boot order is:

```text
Android boot → Termux:Boot → network-service launcher → external guardian
             → PM2/native Node → runtime reconciler → Lite services
```

Termux does not provide `/usr/bin/env`. The recovery scripts therefore resolve
trusted native binaries under `$PREFIX` and invoke PM2 through native Node and
`tailscaled-start` through native Bash. Do not create a `/usr/bin/env` symlink
or run `pm2 resurrect` as a substitute for the guardian. A live but empty PM2
daemon is reconciled from the source-defined Lite topology, and an empty PM2
state is never saved as the next boot snapshot.

The Lite bootstrap installs two executable Termux:Boot entries:

* `~/.termux/boot/00-pocketlab-network-services` starts `sshd` and requests
  `tailscaled` through the native helper, with exact executable-path checks and
  a bounded lock. A Tailscale failure does not block local recovery.
* `~/.termux/boot/pocketlab-lite` starts the external guardian through native
  Termux Bash after its bounded boot delay.

For a bounded manual observation, inspect the sanitized logs and runtime
state:

```bash
sed -n '1,120p' "$HOME/pocket_lab_logs/network-services-boot.log"
sed -n '1,160p' "$HOME/pocket_lab_logs/boot-recovery.log"
ps -A -o pid=,args= | grep -E 'sshd|tailscaled|runtime-guardian' || true
```

If PM2 is online but has no processes, allow the external guardian/reconciler
to rebuild the desired topology. Do not call `pm2 save` while the topology is
empty. A real Android reboot remains a physical operator-owned acceptance
test; manual recovery and bounded process persistence do not prove that
Termux:Boot executed after a reboot.

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
