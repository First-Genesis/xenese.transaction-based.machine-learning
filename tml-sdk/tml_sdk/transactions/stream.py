"""
Transaction Stream
Stream processing for transactions
"""


class TransactionStream:
    """Transaction stream processor"""

    def __init__(self, topic: str):
        self.topic = topic
