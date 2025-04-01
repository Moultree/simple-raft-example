from messages.base_message import BaseMessage


class VoteRequestMessage(BaseMessage):
    def __init__(self, sender_id, term, last_log_index, last_log_term):
        super().__init__(term, sender_id)
        self.last_log_index = last_log_index
        self.last_log_term = last_log_term
