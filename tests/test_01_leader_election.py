import time
from conftest import get_state, NODES


def test_leader_election():
    time.sleep(6)
    leaders = [p for p in NODES if get_state(p) == "Leader"]
    assert len(leaders) == 1, f"Должен быть ровно 1 лидер, обнаружено: {leaders}"
