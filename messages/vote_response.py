from messages.base_message import BaseMessage


class VoteResponseMessage(BaseMessage):
    def __init__(self, sender_id, term, vote_granted):
        super().__init__(term, sender_id)
        self.vote_granted = vote_granted
