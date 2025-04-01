import os
from servers.node import Node

if __name__ == "__main__":
    node_id = os.getenv("NODE_ID")
    peers = os.getenv("PEERS", "").split(",")

    node = Node(node_id, peers)
    node.start_node(port=5000)
