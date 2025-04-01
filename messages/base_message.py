import json


class BaseMessage:
    def __init__(self, term, sender_id):
        self.term = term
        self.sender_id = sender_id

    def to_dict(self):
        return self.__dict__

    @classmethod
    def from_dict(cls, data):
        return cls(**data)
