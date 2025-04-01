from threading import Timer
import logging
from messages.heartbeat import HeartbeatMessage
from messages.vote_request import VoteRequestMessage
from messages.vote_response import VoteResponseMessage
from flask import request, jsonify


class FollowerState:
    def __init__(self, node):
        self.node = node

    def stop(self):
        if self.node.election_timer:
            self.node.election_timer.cancel()

    def initialize(self):
        self.reset_election_timer()

    def reset_election_timer(self):
        if self.node.election_timer:
            self.node.election_timer.cancel()
        self.node.election_timer = Timer(self.node.election_timeout, self.start_election)
        self.node.election_timer.start()

    def start_election(self):
        logging.info(f"[Узел {self.node.node_id}] Не обнаружен лидер, запускаем выборы")
        self.node.become_candidate()

    def append_entries(self):
        data = request.get_json()
        heartbeat = HeartbeatMessage.from_dict(data)

        if heartbeat.term < self.node.current_term:
            return jsonify({"success": False, "reason": "Устаревшая эпоха"}), 200

        if heartbeat.term > self.node.current_term:
            self.node.current_term = heartbeat.term
            self.node.voted_for = None

        self.node.leader_id = heartbeat.sender_id

        logging.info(f"[Узел {self.node.node_id}] Получен heartbeat от лидера {heartbeat.sender_id}")
        self.reset_election_timer()

        entries = data.get('entries', [])
        prev_log_index = data.get('prev_log_index', -1)
        prev_log_term = data.get('prev_log_term', -1)

        if prev_log_index >= len(self.node.message_log):
            return jsonify({"success": False, "reason": "Недостаток логов"}), 200

        if prev_log_index >= 0 and self.node.message_log[prev_log_index]['term'] != prev_log_term:
            return jsonify({"success": False, "reason": "Несовпадение эпохи"}), 200

        if entries:
            self.node.message_log = self.node.message_log[:prev_log_index + 1]
            self.node.message_log.extend(entries)
            logging.info(f"[Узел {self.node.node_id}] Добавлены записи в лог. Последняя запись: {self.node.message_log[-1]}")

        leader_commit = data.get('leader_commit', self.node.commit_index)
        if leader_commit > self.node.commit_index:
            self.node.commit_index = min(leader_commit, len(self.node.message_log) - 1)
            logging.info(f"[Узел {self.node.node_id}] Обновлён commit_index: {self.node.commit_index}")

        return jsonify({"success": True}), 200

    def vote_request(self):
        data = request.get_json()
        vote_request = VoteRequestMessage.from_dict(data)

        if vote_request.term < self.node.current_term:
            response = VoteResponseMessage(
                sender_id=self.node.node_id,
                term=self.node.current_term,
                vote_granted=False
            )
            return jsonify(response.to_dict()), 200

        if vote_request.term > self.node.current_term:
            self.node.current_term = vote_request.term
            self.node.voted_for = None

        if self.node.voted_for is None or self.node.voted_for == vote_request.sender_id:
            logging.info(f"[Узел {self.node.node_id}] Голосует за кандидата {vote_request.sender_id} в эпохе {vote_request.term}")

            self.node.voted_for = vote_request.sender_id
            self.reset_election_timer()

            response = VoteResponseMessage(
                sender_id=self.node.node_id,
                term=self.node.current_term,
                vote_granted=True
            )

            return jsonify(response.to_dict()), 200

        response = VoteResponseMessage(
            sender_id=self.node.node_id,
            term=self.node.current_term,
            vote_granted=False
        )

        return jsonify(response.to_dict()), 200
