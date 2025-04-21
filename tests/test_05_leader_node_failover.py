import time
import requests
import pytest

from conftest import BASE_URL, get_state, get_leader


def test_leader_failover_via_shutdown():
    time.sleep(6)
    original_leader = get_leader()
    assert original_leader is not None, "Не удалось найти изначального лидера"

    resp = requests.post(
        f"{BASE_URL.format(original_leader)}/shutdown",
        timeout=2
    )
    assert resp.status_code == 200, f"Не удалось вызвать shutdown: {resp.text}"
    deadline = time.time() + 40
    while time.time() < deadline:
        try:
            get_state(original_leader)
        except requests.RequestException:
            break
        time.sleep(0.5)
    else:
        pytest.fail("Лидер не выключился в ожидаемое время")

    new_leader = None
    start = time.time()
    while time.time() - start < 10:
        nl = get_leader()
        if nl and nl != original_leader:
            new_leader = nl
            break
        time.sleep(0.5)
    assert new_leader is not None, "Новый лидер не был избран после shutdown"