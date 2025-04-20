import pytest
from conftest import NODES, get_state


def test_all_nodes_return_valid_state(cluster):
    valid = {"Follower", "Leader"}
    for port in NODES:
        state = get_state(port)
        assert state in valid, f"Узел на порту {port} вернул некорректное состояние: {state}"