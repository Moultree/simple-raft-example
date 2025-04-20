import time
import requests

from conftest import NODES, BASE_URL, get_leader, get_logs


def test_log_replication():
    leader = get_leader()
    assert leader is not None, "Лидер не найден"

    resp = requests.post(
        BASE_URL.format(leader) + "/client_request",
        json={"message": "integration-test-entry"},
        timeout=2
    )
    assert resp.status_code == 200

    time.sleep(2)
    for p in NODES:
        logs = get_logs(p)
        assert any("integration-test-entry" in str(e) for e in logs), (
            f"Узел {p} не реплицировал запись: {logs}"
        )
