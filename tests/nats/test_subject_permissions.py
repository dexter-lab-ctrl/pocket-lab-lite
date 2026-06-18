import fnmatch

PERMISSIONS = {
    "api": {
        "pub": [
            "pocketlab.commands.*",
            "pocketlab.events.*",
            "pocketlab.audit.*",
            "pocketlab.dlq.*",
        ],
        "sub": ["_INBOX.*", "pocketlab.events.*", "pocketlab.audit.*"],
    },
    "worker": {
        "pub": ["pocketlab.events.*", "pocketlab.audit.*", "pocketlab.dlq.*"],
        "sub": ["_INBOX.*", "pocketlab.commands.*"],
    },
    "agent": {
        "pub": [
            "pocketlab.events.fleet.*",
            "pocketlab.events.telemetry.*",
            "pocketlab.events.health.*",
        ],
        "sub": ["_INBOX.*", "pocketlab.commands.node.*"],
    },
}


def allowed(role, action, subject):
    return any(
        fnmatch.fnmatch(subject, pattern) for pattern in PERMISSIONS[role][action]
    )


def test_api_can_publish_typed_operations():
    assert allowed("api", "pub", "pocketlab.commands.operation.execute")
    assert allowed("api", "pub", "pocketlab.commands.vault.rotate")
    assert allowed("api", "pub", "pocketlab.commands.fleet.join")


def test_worker_consumes_commands_and_publishes_events():
    assert allowed("worker", "sub", "pocketlab.commands.operation.execute")
    assert allowed("worker", "pub", "pocketlab.events.operation.completed")
    assert allowed("worker", "pub", "pocketlab.audit.operation")
    assert allowed("worker", "pub", "pocketlab.dlq.operation")


def test_agent_is_node_scoped_and_cannot_subscribe_all_commands():
    assert allowed("agent", "pub", "pocketlab.events.fleet.heartbeat")
    assert allowed("agent", "sub", "pocketlab.commands.node.android-lab-01")
    assert not allowed("agent", "sub", "pocketlab.commands.operation.execute")
