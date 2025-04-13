from flask import Flask, request, jsonify
import requests
import threading
import time
import logging
import random
from servers.follower import FollowerState
from servers.candidate import CandidateState
from servers.leader import LeaderState
import docker


class Node:
    def __init__(self, node_id, peers):
        self.node_id = node_id
        self.peers = peers
        self.app = Flask(__name__)
        self.is_leader = False
        self.message_log = []
        self.election_timer = None
        self.state = "Follower"
        self.election_timeout = random.uniform(3, 5)
        self.current_term = 0
        self.commit_index = 0
        self.current_state = None
        self.docker_client = docker.from_env()
        self.container_name = f"raft-containter-node:{node_id}"
        self.logger = logging.getLogger("raft")

        self.app.add_url_rule(
            "/receive_message",
            "receive_message",
            self.receive_message,
            methods=["POST"],
        )
        self.app.add_url_rule(
            "/send_message", "send_message", self.send_message, methods=["POST"]
        )
        self.app.add_url_rule(
            "/message_log", "get_message_log", self.get_message_log, methods=["GET"]
        )
        self.app.add_url_rule("/state", "get_state", self.get_state, methods=["GET"])
        self.app.add_url_rule(
            "/append_entries", "append_entries", self.append_entries, methods=["POST"]
        )
        self.app.add_url_rule(
            "/vote_request", "vote_request", self.vote_request, methods=["POST"]
        )
        self.app.add_url_rule("/shutdown", "shutdown", self.shutdown, methods=["POST"])
        self.app.add_url_rule(
            "/client_request", "client_request", self.client_request, methods=["POST"]
        )

    def shutdown(self):
        try:
            duration = 30

            def delayed_restart():
                try:
                    container = self.docker_client.containers.get(self.container_name)
                    container.stop()
                    self.logger.info(f"[Узел {self.node_id}] Контейнер остановлен")

                    time.sleep(duration)

                    container.start()
                    self.logger.info(
                        f"[Узел {self.node_id}] Контейнер перезапущен через {duration} секунд"
                    )

                except docker.errors.NotFound:
                    self.logger.error(
                        f"[Узел {self.node_id}] Контейнер не найден: {self.container_name}"
                    )
                except Exception as e:
                    self.logger.error(
                        f"[Узел {self.node_id}] Ошибка при отключении/перезапуске: {str(e)}"
                    )

            threading.Thread(target=delayed_restart).start()

            return (
                jsonify(
                    {"status": f"Отключение узла инициировано на {duration} секунд"}
                ),
                200,
            )
        except Exception as e:
            self.logger.error(f"[Узел {self.node_id}] Ошибка при отключении: {str(e)}")
            return jsonify({"error": str(e)}), 500

    def initialize(self):
        self.become_follower()

    def start_node(self, port):
        threading.Thread(target=self.run_flask_server, args=(port,)).start()
        time.sleep(1)
        self.initialize()

    def run_flask_server(self, port):
        try:
            self.app.run(host="0.0.0.0", port=port, threaded=True)
        except Exception as e:
            self.logger.error(f"Ошибка сервера: {e}")

    def become_follower(self):
        if self.current_state and hasattr(self.current_state, "stop"):
            self.current_state.stop()
        self.state = "Follower"
        self.current_state = FollowerState(self)
        self.logger.info(f"[Узел {self.node_id}] Перешёл в состояние Follower")
        self.current_state.initialize()

    def become_candidate(self):
        if self.current_state and hasattr(self.current_state, "stop"):
            self.current_state.stop()
        self.state = "Candidate"
        self.current_state = CandidateState(self)
        self.logger.info(f"[Узел {self.node_id}] Перешёл в состояние Candidate")
        self.current_state.start()

    def become_leader(self):
        if self.current_state and hasattr(self.current_state, "stop"):
            self.current_state.stop()
        self.state = "Leader"
        self.current_state = LeaderState(self)
        self.logger.info(f"[Узел {self.node_id}] Перешёл в состояние Leader")
        self.current_state.start_leader()

    def receive_message(self):
        data = request.get_json()
        sender = data.get("sender")
        message = data.get("message")

        self.message_log.append((sender, message))

        self.logger.info(
            f"[Узел {self.node_id}] Получено сообщение от узла {sender}: {message}"
        )
        return jsonify({"status": "Сообщение получено"}), 200

    def send_message(self):
        data = request.get_json()
        message = data.get("message")

        for peer in self.peers:
            host, port = peer.split(":")
            url = f"http://{host}:5000/receive_message"
            try:
                response = requests.post(
                    url, json={"sender": self.node_id, "message": message}
                )
                if response.status_code == 200:
                    self.logger.info(
                        f"[Узел {self.node_id}] Отправлено сообщение на {peer}: {message}"
                    )
            except requests.ConnectionError:
                self.logger.info(f"[Узел {self.node_id}] Не удалось связаться с {peer}")

        return jsonify({"status": "Сообщение отправлено всем узлам"}), 200

    def get_message_log(self):
        return jsonify({"messages": self.message_log}), 200

    def get_state(self):
        return jsonify({"state": self.state, "node_id": self.node_id}), 200

    def append_entries(self):
        return self.current_state.append_entries()

    def vote_request(self):
        return self.current_state.vote_request()

    def process_client_request(self, message):
        self.current_state.send_append_entries_to_followers(message)

    def client_request(self):
        data = request.get_json()
        message = data.get("message")
        self.logger.info(f"[Узел {self.node_id}] получил клиентский запрос")

        if self.state != "Leader" or not isinstance(self.current_state, LeaderState):
            if hasattr(self, "leader_id") and self.leader_id:
                leader_peer = next(
                    (
                        peer
                        for peer in self.peers
                        if peer.startswith(f"node{self.leader_id}:")
                    ),
                    None,
                )
                if leader_peer:
                    host, port = leader_peer.split(":")
                    leader_address = f"http://{host}:5000"
                    return (
                        jsonify({"error": "Узел не лидер", "leader": leader_address}),
                        400,
                    )
            return jsonify({"error": "Узел не лидер"}), 400
        else:
            self.process_client_request(message)
            return jsonify({"status": "Сообщение получено и реплицировано"}), 200
