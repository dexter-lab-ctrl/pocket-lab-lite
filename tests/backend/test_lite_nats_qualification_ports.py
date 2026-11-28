from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
START_DASHBOARD = ROOT / "pocket-lab-final-structure" / "pocket-lab-bootstrap-production-scripts-patched" / "scripts" / "start-dashboard.sh"


def test_nats_qualification_ports_are_explicit_and_loopback_bound() -> None:
    source = START_DASHBOARD.read_text(encoding="utf-8")
    assert 'POCKETLAB_LITE_NATS_PORT:-${POCKETLAB_PUBLIC_NATS_PORT:-4222}' in source
    assert 'POCKETLAB_LITE_NATS_MONITOR_PORT:-${POCKETLAB_PUBLIC_NATS_MONITOR_PORT:-8222}' in source
    assert 'nats_listen_host="${POCKETLAB_NATS_LISTEN_HOST:-0.0.0.0}"' in source
    assert '[[ "$nats_listen_host" == "127.0.0.1" ]] || die "Qualification NATS must bind to loopback"' in source
    assert 'listen: $nats_listen_host:$nats_port' in source
    assert 'http: 127.0.0.1:$nats_monitor_port' in source
    assert 'local monitor_port="${POCKETLAB_LITE_NATS_MONITOR_PORT:-${POCKETLAB_PUBLIC_NATS_MONITOR_PORT:-8222}}"' in source
