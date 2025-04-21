import time
import requests
import pytest

from conftest import NODES, BASE_URL, get_state, get_leader


def test_shutdown_non_leader_preserves_cluster():
    time.sleep(6)
    leader = get_leader()
    assert leader is not None, "Не нашли изначального лидера"

    follower = next(p for p in NODES if p != leader)
    other = next(p for p in NODES if p not in (leader, follower))

    resp = requests.post(
        f"{BASE_URL.format(follower)}/shutdown",
        timeout=2
    )
    assert resp.status_code == 200, f"Shutdown фолловера вернул {resp.status_code}"

    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            state = get_state(follower)
        except requests.RequestException:
            state = "Unavailable"
        if state == "Unavailable":
            break
        time.sleep(1)
    else:
        pytest.fail(f"Follower {follower} всё ещё отвечает после 30 s")

    assert get_leader() == leader, "Лидер заменился после shutdown фолловера"

    try:
        st = get_state(follower)
    except requests.RequestException:
        st = "Unavailable"
    assert st == "Unavailable", "Целевой фолловер всё ещё доступен после shutdown"

    st_other = get_state(other)
    assert st_other == "Follower", (
        f"Второй фолловер неожиданно не Follower после shutdown: {st_other}"
    )