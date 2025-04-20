.PHONY: test
test: test-01 test-02 test-03 test-04 

test-00:
	pytest tests/test_00_smoke_cluster.py

test-01:
	pytest tests/test_01_leader_election.py

test-02:
	pytest tests/test_02_log_replication.py

test-03:
	pytest tests/test_03_message_replication.py

test-04:
	pytest tests/test_04_client_redirection.py
