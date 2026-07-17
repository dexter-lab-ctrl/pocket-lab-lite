from pathlib import Path


def test_s6_server_phone_gate_is_termux_safe_and_non_destructive():
    script = Path(
        "scripts/dev/check-lite-security-s6-backend-gate-server-phone.sh"
    ).read_text(encoding="utf-8")

    assert '${TMPDIR:-${PREFIX:-$HOME}/tmp}' in script
    assert "> /tmp/" not in script
    assert "mktemp -d" in script
    assert "curl exit $rc" in script
    assert '"$rc" -ne 0 && "$rc" -ne 28' in script
    assert "Last-Event-ID: $cursor" in script
    assert "PRAGMA quick_check" in script
    assert ".backup '$RESET_DB'" in script
    assert ".backup '$RET_DB'" in script
    assert "0 < int(first.get(\"rows_deleted\") or 0) <= 25" in script
    assert "progress_retention:last" in script
    assert "production database unchanged by pressure tests" in script


def test_s6_server_phone_gate_uses_real_schema_and_sql_literals():
    script = Path(
        "scripts/dev/check-lite-security-s6-backend-gate-server-phone.sh"
    ).read_text(encoding="utf-8")

    assert "current_stage" not in script
    assert "current_percent" not in script
    assert "event_type," not in script
    assert 'status IN (\'queued\',\'accepted\',\'running\',\'working\',\'in_progress\')' in script
    assert "return 1 2>/dev/null || exit 1" not in script
    assert "set -e" not in script


def test_s6_server_phone_gate_parses_progress_fields_and_allows_heartbeat_margin():
    script = Path(
        "scripts/dev/check-lite-security-s6-backend-gate-server-phone.sh"
    ).read_text(encoding="utf-8")

    assert 'POCKETLAB_S6_GATE_SSE_CAPTURE_SECONDS:-35' in script
    assert "IFS=$'\\t' read -r ACTIVE RUN_ID" in script
    assert "IFS=$'\\t' read -r ACTIVE CURRENT_RUN" in script
    assert '+ "\\t" + (p.get("run_id") or "")' in script
    assert 'print("1" if p.get("active_scan") else "0", p.get("run_id") or "")' not in script
