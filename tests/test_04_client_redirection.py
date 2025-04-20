import pytest
import requests
from urllib.parse import urlparse
from conftest import NODES, BASE_URL, get_leader, LOCAL_TO_NODE


def test_client_redirection_to_leader(cluster):
    leader = get_leader()
    assert leader is not None, "Не удалось определить лидера"
    follower = next(p for p in NODES if p != leader)

    message = "redirect-test"
    url = f"{BASE_URL.format(follower)}/client_request"
    resp = requests.post(url, json={"message": message}, timeout=1)

    assert resp.status_code == 400, f"Ожидался 400 от фолловера, получили {resp.status_code}"
    data = resp.json()
    assert data.get("error") == "Узел не лидер", f"Неверное тело ответа: {data}"
    leader_url = data.get("leader")
    assert leader_url, "Фолловер не указал адрес лидера"

    parsed = urlparse(leader_url)
    base = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
    expected = LOCAL_TO_NODE[f"localhost:{leader}"].rstrip('/')

    assert base == expected, (
        f"Неверный leader URL: {leader_url}, ожидали {expected}"
    )