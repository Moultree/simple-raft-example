import logging
import requests
import threading
from messages.heartbeat import HeartbeatMessage
from messages.vote_response import VoteResponseMessage
from messages.vote_request import VoteRequestMessage
from flask import request, jsonify
import sqlite3


class LeaderState:
    def __init__(self, node):
        self.node = node
        self.heartbeat_interval = 0.5
        self.heartbeat_timer = None
        self.next_index = {peer: len(self.node.message_log) for peer in self.node.peers}
        self.match_index = {peer: 0 for peer in self.node.peers}
        self.replication_threshold = 1
        self.logger = logging.getLogger("raft")

    def start_leader(self):
        self.send_heartbeats()
        self.initialize_database()

    def send_heartbeats(self):
        self.logger.info(
            f"[Узел {self.node.node_id}] Отправка heartbeat-сообщений всем узлам"
        )
        for peer in self.node.peers:
            next_idx = self.next_index[peer]
            prev_log_index = next_idx - 1
            prev_log_term = (
                self.node.message_log[prev_log_index]["term"]
                if prev_log_index >= 0
                else -1
            )
            entries = self.node.message_log[next_idx:]

            heartbeat_message = HeartbeatMessage(
                sender_id=self.node.node_id,
                term=self.node.current_term,
                prev_log_index=prev_log_index,
                prev_log_term=prev_log_term,
                leader_commit=self.node.commit_index,
                entries=entries,
            )
            message_dict = heartbeat_message.to_dict()

            try:
                host, port = peer.split(":")
                response = requests.post(
                    f"http://{host}:5000/append_entries", json=message_dict, timeout=(1.0, 2.0)
                )

                self.logger.debug(
                    f"[Узел {self.node.node_id}] Отправлено heartbeat-сообщение на {peer}: {message_dict}"
                )

                self.logger.debug(
                    f"[Узел {self.node.node_id}] Получен ответ от {peer}: {response.status_code}"
                )
                if response.status_code == 200:
                    data = response.json()

                    if data.get("success"):
                        self.match_index[peer] = prev_log_index + len(entries)
                        self.next_index[peer] = self.match_index[peer] + 1
                        self.logger.info(
                            f"[Узел {self.node.node_id}] Отправлен heartbeat на {peer}"
                        )
                    else:
                        self.next_index[peer] -= 1
                        self.logger.warning(
                            f"[Узел {self.node.node_id}] Не удалось добавить записи на {peer}. {data.get('reason')}"
                        )
                else:
                    self.logger.warning(
                        f"[Узел {self.node.node_id}] Не удалось отправить heartbeat на {peer}. {response.status_code}"
                    )
            except requests.RequestException:
                self.logger.warning(
                    f"[Узел {self.node.node_id}] Не удалось отправить heartbeat на {peer}: {e}"
                )

        self.heartbeat_timer = threading.Timer(
            self.heartbeat_interval, self.send_heartbeats
        )
        self.heartbeat_timer.start()

    def initialize_database(self):
        db_path = "/app/disk/leader_logs.db"
        self.db_path = db_path
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT,
                    term INTEGER,
                    message TEXT,
                    commit_index INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    leader_id TEXT
            )
            """
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            self.logger.error(f"Failed to initialize database: {e}")

    def send_append_entries_to_followers(self, message):
        self.node.message_log.append(
            {
                "node_id": self.node.node_id,
                "term": self.node.current_term,
                "message": message,
            }
        )

        current_entry_index = len(self.node.message_log) - 1
        success_count = 0

        for peer in self.node.peers:
            host, port = peer.split(":")
            url = f"http://{host}:5000/append_entries"
            prev_log_index = current_entry_index - 1
            prev_log_term = (
                self.node.message_log[prev_log_index]["term"]
                if prev_log_index >= 0
                else -1
            )
            entries = [self.node.message_log[current_entry_index]]
            append_entries_msg = HeartbeatMessage(
                sender_id=self.node.node_id,
                term=self.node.current_term,
                prev_log_index=prev_log_index,
                prev_log_term=prev_log_term,
                leader_commit=self.node.commit_index,
                entries=entries,
            )
            try:
                response = requests.post(url, json=append_entries_msg.to_dict())
                if response.status_code == 200:
                    data = response.json()
                    if data.get("term", self.node.current_term) > self.node.current_term:
                        self.logger.info(
                            f"[Узел {self.node.node_id}] Обнаружен более новый term {data['term']} от {peer}, демотируюсь в Follower"
                        )
                        self.node.current_term = data["term"]
                        self.node.become_follower()
                        return
                    elif data.get("success"):
                        self.match_index[peer] = current_entry_index
                        success_count += 1
                        self.logger.info(
                            f"[Узел {self.node.node_id}] Успешно реплицирована запись на {peer}"
                        )
                    else:
                        self.logger.warning(
                            f"[Узел {self.node.node_id}] Ошибка репликации записи на {peer} {data.get('reason')}"
                        )
                else:
                    self.logger.warning(
                        f"[Узел {self.node.node_id}] Не удалось реплицировать запись на {peer} {response.status_code}"
                    )
            except requests.exceptions.RequestException:
                self.logger.warning(
                    f"[Узел {self.node.node_id}] Исключение при репликации на {peer}"
                )

        if success_count >= (len(self.node.peers) + 1) // 2:
            self.node.commit_index = current_entry_index
            self.save_to_disk(self.node.message_log[current_entry_index])

    def save_to_disk(self, entry):
        entry_data = {
            "node_id": entry["node_id"],
            "term": entry["term"],
            "message": entry["message"],
            "commit_index": self.node.commit_index,
            "leader_id": self.node.node_id,
        }
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO logs (node_id, term, message, commit_index, leader_id)
                VALUES (:node_id, :term, :message, :commit_index, :leader_id)
                """,
                entry_data,
            )
            conn.commit()
            conn.close()
            self.logger.info("Запись успешно сохранена в базу данных")
        except sqlite3.Error as e:
            self.logger.error(f"Не удалось сохранить запись в базу данных. Ошибка: {e}")

    def stop(self):
        if self.heartbeat_timer:
            self.heartbeat_timer.cancel()
            self.heartbeat_timer = None

    def vote_request(self):
        data = request.get_json()
        vote_request = VoteRequestMessage.from_dict(data)
        if vote_request.term > self.node.current_term:
            self.node.current_term = vote_request.term
            self.node.become_follower()
            return self.node.current_state.vote_request()
        else:
            response = VoteResponseMessage(
                sender_id=self.node.node_id,
                term=self.node.current_term,
                vote_granted=False,
            )
            return jsonify(response.to_dict()), 200
