"""Send an unprivileged desktop notification, independently of cyberlabd."""

import argparse
import asyncio
from html import escape
import sys

from dbus_next import BusType, Message, MessageType
from dbus_next.aio import MessageBus


async def notify(title, body):
    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    try:
        response = await bus.call(Message(
            destination="org.freedesktop.Notifications", path="/org/freedesktop/Notifications",
            interface="org.freedesktop.Notifications", member="Notify", signature="susssasa{sv}i",
            body=["CyberLab", 0, "dialog-information", title[:160], escape(body[:4096]), [], {}, 6000],
        ))
        if response.message_type == MessageType.ERROR:
            raise RuntimeError("Desktop notification service is unavailable")
    finally:
        bus.disconnect()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("title")
    parser.add_argument("body")
    arguments = parser.parse_args()
    try:
        asyncio.run(asyncio.wait_for(notify(arguments.title, arguments.body), timeout=5))
    except Exception:
        print("CyberLab: desktop notification unavailable", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
