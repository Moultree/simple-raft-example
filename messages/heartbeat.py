from messages.base_message import BaseMessage


class HeartbeatMessage(BaseMessage):
    def __init__(
        self,
        sender_id,
        term,
        prev_log_index,
        prev_log_term,
        leader_commit,
        entries=None,
    ):
        super().__init__(term, sender_id)
        self.prev_log_index = prev_log_index
        self.prev_log_term = prev_log_term
        self.leader_commit = leader_commit
        self.entries = entries or []

    def to_dict(self):
        return {
            "sender_id": self.sender_id,
            "term": self.term,
            "prev_log_index": self.prev_log_index,
            "prev_log_term": self.prev_log_term,
            "leader_commit": self.leader_commit,
            "entries": self.entries,
        }
