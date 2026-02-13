"""ZeroMQ SUB socket for remotely monitoring bot state."""
import json


class ZMQSubscriber:
    """Subscribe to bot events via ZeroMQ. No-op if pyzmq is not installed."""

    def __init__(self, host="localhost", port=5555, topics=None):
        self._available = False
        self._socket = None
        self._context = None
        try:
            import zmq
            self._zmq = zmq
            self._context = zmq.Context()
            self._socket = self._context.socket(zmq.SUB)
            self._socket.connect(f"tcp://{host}:{port}")

            if topics:
                for topic in topics:
                    self._socket.setsockopt_string(zmq.SUBSCRIBE, topic)
            else:
                self._socket.setsockopt_string(zmq.SUBSCRIBE, "")

            self._available = True
        except ImportError:
            pass

    @property
    def available(self):
        return self._available

    def receive(self, timeout_ms=1000):
        """Receive a message with timeout.

        Returns (topic, data_dict) or None if timeout or unavailable.
        """
        if not self._available:
            return None

        poller = self._zmq.Poller()
        poller.register(self._socket, self._zmq.POLLIN)
        socks = dict(poller.poll(timeout_ms))

        if self._socket in socks:
            raw = self._socket.recv_string()
            space_idx = raw.index(" ")
            topic = raw[:space_idx]
            data = json.loads(raw[space_idx + 1:])
            return topic, data

        return None

    def close(self):
        """Clean up ZMQ resources."""
        if self._available and self._socket:
            self._socket.close()
            self._context.term()
            self._available = False
