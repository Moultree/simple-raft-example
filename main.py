import os
import logging
from servers.node import Node

node_id = os.getenv("NODE_ID")
peers = os.getenv("PEERS", "").split(",")
port = int(os.getenv("PORT", 5000))
log_path = f"/app/logs/node_{node_id}.log"

logger = logging.getLogger("raft")
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(log_path)
file_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s'))
logger.addHandler(console_handler)
logger.propagate = False

werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.DEBUG)
werkzeug_logger.addHandler(file_handler)

if __name__ == "__main__":
    node = Node(node_id=node_id, peers=peers)
    node.start_node(port=port)
