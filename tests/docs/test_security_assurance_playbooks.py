from __future__ import annotations

from scripts.docs.check_security_assurance_playbooks import collect_errors


def test_security_assurance_playbook_contract_is_current_and_complete():
    assert collect_errors() == []
