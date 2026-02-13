"""Tests for monitoring ZMQ publisher and subscriber."""
import unittest

from monitoring.zmq_publisher import ZMQPublisher
from monitoring.zmq_subscriber import ZMQSubscriber


class TestZMQMonitoring(unittest.TestCase):

    def test_publisher_noop_without_zmq(self):
        """If zmq is not available, publish() is a silent no-op."""
        pub = ZMQPublisher.__new__(ZMQPublisher)
        pub._available = False
        pub._socket = None
        pub._context = None

        # Should not raise
        pub.publish("test", {"key": "value"})
        pub.close()
        self.assertFalse(pub.available)

    def test_pub_sub_roundtrip(self):
        """Publisher sends message, subscriber receives it (if zmq available)."""
        try:
            import zmq
        except ImportError:
            self.skipTest("pyzmq not installed")

        import time

        pub = ZMQPublisher(port=15555)
        sub = ZMQSubscriber(host="localhost", port=15555)

        self.assertTrue(pub.available)
        self.assertTrue(sub.available)

        # Give ZMQ time to establish connection
        time.sleep(0.5)

        pub.publish("test_topic", {"hello": "world"})
        time.sleep(0.1)

        msg = sub.receive(timeout_ms=2000)
        self.assertIsNotNone(msg)
        topic, data = msg
        self.assertEqual(topic, "test_topic")
        self.assertEqual(data["hello"], "world")

        pub.close()
        sub.close()


if __name__ == "__main__":
    unittest.main()
