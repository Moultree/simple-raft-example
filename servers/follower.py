from threading import Timer
import logging
from messages.heartbeat import HeartbeatMessage
from messages.vote_request import VoteRequestMessage
from messages.vote_response import VoteResponseMessage
from flask import request, jsonify


class FollowerState:
    def __init__(self, node):
        self.node = node
        self.logger = logging.getLogger("raft")

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
        self.logger.info(f"[Узел {self.node.node_id}] Не обнаружен лидер, запускаем выборы")
        self.node.become_candidate()

    def append_entries(self):
        data = request.get_json()
        heartbeat = HeartbeatMessage.from_dict(data)

        if heartbeat.term < self.node.current_term:
            return jsonify({"success": False, "reason": "Устаревшая эпоха"}), 200

        if heartbeat.term > self.node.current_term:
            self.node.current_term = heartbeat.term
            self.node.voted_for = None
            self.node.become_follower()

        self.node.leader_id = heartbeat.sender_id

        logging.info(f"[Узел {self.node.node_id}] Получен heartbeat от лидера {heartbeat.sender_id}")
        self.reset_election_timer()

        prev_log_index = heartbeat.prev_log_index
        prev_log_term = heartbeat.prev_log_term

        if prev_log_index >= len(self.node.message_log):
            return jsonify({"success": False, "reason": "Недостаток логов"}), 200

        if prev_log_index >= 0 and self.node.message_log[prev_log_index]["term"] != prev_log_term:
            self.logger.warning(
                f"[Узел {self.node.node_id}] Конфликт логов. Удаление с индекса {prev_log_index} и далее"
            )
            self.node.message_log = self.node.message_log[:prev_log_index]
            return jsonify({"success": False, "reason": "Конфликтующие сущности удалены"}), 200

        entries = heartbeat.entries
        if entries:
            self.node.message_log = self.node.message_log[:prev_log_index + 1]
            self.node.message_log.extend(entries)
            self.logger.info(
                f"[Узел {self.node.node_id}] Добавлены записи: {entries[-1] if entries else '—'}"
            )

        if heartbeat.leader_commit > self.node.commit_index:
            self.node.commit_index = min(
                heartbeat.leader_commit, len(self.node.message_log) - 1
            )
            self.logger.info(
                f"[Узел {self.node.node_id}] Обновлён commit_index до {self.node.commit_index}"
            )

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
            self.logger.info(f"[Узел {self.node.node_id}] Голосует за кандидата {vote_request.sender_id} в эпохе {vote_request.term}")

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
