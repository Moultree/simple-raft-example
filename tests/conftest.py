import subprocess
import time
import pytest
import requests
import os

NODES = ["6500", "6501", "6502"]
BASE_URL = "http://localhost:{}"

LOCAL_TO_NODE = {
    "localhost:6500": "http://node1:5000",
    "localhost:6501": "http://node2:5000",
    "localhost:6502": "http://node3:5000",
}


def all_nodes_responsive(timeout=1):
    """Проверяет, что каждый узел отвечает на /state за timeout секунд."""
    for port in NODES:
        try:
            r = requests.get(BASE_URL.format(port) + "/state", timeout=timeout)
            if r.status_code != 200:
                return False
        except requests.RequestException:
            return False
    return True


@pytest.fixture(autouse=True)
def cluster():
    for port in range(1, 4):
        path = f"./logs/node_{port}.log"
        if os.path.exists(path):
            os.remove(path)

    subprocess.run(["docker-compose", "down", "-v"], check=True)
    subprocess.run(["docker-compose", "up", "-d"], check=True)
    time.sleep(10)

    start = time.time()
    while time.time() - start < 40:
        if all_nodes_responsive():
            break
        time.sleep(1)
    else:
        pytest.skip("Кластер не поднялся в отведённое время")

    yield

    subprocess.run(["docker-compose", "down", "-v"], check=True)


def get_state(port):
    r = requests.get(BASE_URL.format(port) + "/state", timeout=1)
    return r.json().get("state")


def get_leader():
    for p in NODES:
        try:
            r = requests.get(BASE_URL.format(p) + "/state", timeout=1)
            if r.json().get("state") == "Leader":
                return p
        except requests.RequestException:
            continue
    return None


def get_logs(port):
    r = requests.get(BASE_URL.format(port) + "/message_log", timeout=1)
    return r.json().get("messages", [])
