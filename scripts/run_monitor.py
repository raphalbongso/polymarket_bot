"""Monitor a running Polymarket bot via ZeroMQ.

Usage:
    python scripts/run_monitor.py
    python scripts/run_monitor.py --host 192.168.1.100 --port 5555
    python scripts/run_monitor.py --topics trade,risk,kill
"""
import argparse
import json
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monitoring.zmq_subscriber import ZMQSubscriber


def main():
    parser = argparse.ArgumentParser(description="Monitor Polymarket bot")
    parser.add_argument("--host", default="localhost", help="Bot host address")
    parser.add_argument("--port", type=int, default=5555, help="ZMQ port")
    parser.add_argument("--topics", default="", help="Comma-separated topics to filter")
    args = parser.parse_args()

    topics = [t.strip() for t in args.topics.split(",") if t.strip()] or None

    print(f"Connecting to bot at {args.host}:{args.port}...")
    if topics:
        print(f"Filtering topics: {topics}")

    subscriber = ZMQSubscriber(host=args.host, port=args.port, topics=topics)

    if not subscriber.available:
        print("ERROR: pyzmq is not installed. Run: pip install pyzmq")
        sys.exit(1)

    print("Listening for events (Ctrl+C to quit)...\n")
    last_heartbeat = time.time()

    try:
        while True:
            msg = subscriber.receive(timeout_ms=2000)
            if msg:
                topic, data = msg
                last_heartbeat = time.time()
                timestamp = data.get("timestamp", "")
                print(f"[{topic.upper():>10}] {json.dumps(data, indent=2)}")
            else:
                silence = time.time() - last_heartbeat
                if silence > 30:
                    print(f"WARNING: No heartbeat for {silence:.0f}s — bot may be down")
    except KeyboardInterrupt:
        print("\nMonitor stopped.")
    finally:
        subscriber.close()


if __name__ == "__main__":
    main()
