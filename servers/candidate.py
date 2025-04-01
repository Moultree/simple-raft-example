import logging
import requests
from messages.vote_request import VoteRequestMessage
from messages.vote_response import VoteResponseMessage


class CandidateState:
    def __init__(self, node):
        self.node = node

    def start(self):
        self.start_election()

    def start_election(self):
        logging.info(f"[Узел {self.node.node_id}] запускает выборы")
        self.increment_term()
        self.reset_votes()
        self.send_vote_requests()
        self.evaluate_election_result()

    def increment_term(self):
        self.node.current_term += 1

    def reset_votes(self):
        self.node.votes = 1
        self.node.voted_for = self.node.node_id

    def send_vote_requests(self):
        last_log_index = (
            len(self.node.message_log) - 1 if len(self.node.message_log) > 0 else -1
        )
        last_log_term = (
            self.node.message_log[last_log_index]["term"] if last_log_index >= 0 else -1
        )

        vote_request = VoteRequestMessage(
            sender_id=self.node.node_id,
            term=self.node.current_term,
            last_log_index=last_log_index,
            last_log_term=last_log_term,
        )
        request_dict = vote_request.to_dict()

        for peer in self.node.peers:
            try:
                host, port = peer.split(":")
                response = requests.post(
                    f"http://{host}:5000/vote_request", json=request_dict
                )

                if response.status_code == 200:
                    vote_response = VoteResponseMessage.from_dict(response.json())

                    self.process_vote_response(vote_response, peer)

            except requests.ConnectionError:
                logging.warning(
                    f"[Узлу {self.node.node_id}] не удалось связаться с {peer} во время выборов"
                )

    def process_vote_response(self, vote_response, peer):
        if vote_response.vote_granted:
            self.node.votes += 1
        elif vote_response.term > self.node.current_term:
            logging.info(
                f"[Узел {self.node.node_id}] Обнаружен более новая эпоха от {peer}, переключение в ведомого"
            )
            self.node.current_term = vote_response.term
            self.node.become_follower()
            return

    def evaluate_election_result(self):
        if self.node.votes > len(self.node.peers) // 2:
            logging.info(
                f"[Узел {self.node.node_id}] Выиграл выборы, становится лидером"
            )
            self.node.become_leader()
        else:
            logging.info(
                f"[Узел {self.node.node_id}] Проиграл выборы, становится ведомым"
            )
            self.node.become_follower()

    def stop(self):
        self.node.current_state = None
        if hasattr(self, "retry_election_timer"):
            self.retry_election_timer.cancel()
