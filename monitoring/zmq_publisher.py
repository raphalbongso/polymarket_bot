"""ZeroMQ PUB socket for broadcasting bot state to remote monitors."""
import json


class ZMQPublisher:
    """Publish bot events via ZeroMQ. No-op if pyzmq is not installed."""

    def __init__(self, port=5555):
        self._available = False
        self._socket = None
        self._context = None
        try:
            import zmq
            self._context = zmq.Context()
            self._socket = self._context.socket(zmq.PUB)
            self._socket.bind(f"tcp://*:{port}")
            self._available = True
        except ImportError:
            pass

    @property
    def available(self):
        return self._available

    def publish(self, topic, data):
        """Publish a JSON message on a topic.

        Topics: 'trade', 'signal', 'risk', 'heartbeat', 'kill'
        """
        if not self._available:
            return
        message = json.dumps(data)
        self._socket.send_string(f"{topic} {message}")

    def close(self):
        """Clean up ZMQ resources."""
        if self._available and self._socket:
            self._socket.close()
            self._context.term()
            self._available = False
