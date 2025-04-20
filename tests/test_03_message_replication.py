import time
import pytest
import requests
from conftest import NODES, BASE_URL, get_leader, get_logs


def test_message_replication(cluster):
    leader = get_leader()
    assert leader is not None, "Не удалось определить лидера"

    message = "hello-from-test"
    url = f"{BASE_URL.format(leader)}/client_request"
    resp = requests.post(url, json={"message": message}, timeout=1)
    assert resp.status_code == 200, f"client_request failed: {resp.text}"

    time.sleep(1)

    for port in NODES:
        logs = get_logs(port)

        messages = [entry.get('message') for entry in logs if isinstance(entry, dict)]
        assert message in messages, f"Узел {port} не получил сообщение: {message}, logs: {logs}"
