#!/usr/bin/env python3
"""Keep a localhost WSL CDP port backed by outbound Windows relay channels.

The Windows Chrome CDP forward is intentionally bound to Windows loopback and
cannot be reached from native WSL. This small, qualification-owned relay keeps
the WSL controller local while Windows opens outbound channels to it. It never
binds a Windows listener, changes firewall policy, or exposes CDP to the LAN.
"""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
from dataclasses import dataclass


CHANNEL_HELLO = b"PLR1"
CHANNEL_USE = b"USE1"


@dataclass
class RelaySlot:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    assigned: asyncio.Event
    done: asyncio.Event


async def pipe(source: asyncio.StreamReader, destination: asyncio.StreamWriter) -> None:
    try:
        while data := await source.read(64 * 1024):
            destination.write(data)
            await destination.drain()
    except (ConnectionError, asyncio.IncompleteReadError):
        pass


async def bridge(
    local_reader: asyncio.StreamReader,
    local_writer: asyncio.StreamWriter,
    slot: RelaySlot,
) -> None:
    slot.assigned.set()
    slot.writer.write(CHANNEL_USE)
    await slot.writer.drain()
    forward = asyncio.create_task(pipe(local_reader, slot.writer))
    reverse = asyncio.create_task(pipe(slot.reader, local_writer))
    try:
        await asyncio.wait([forward, reverse], return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in (forward, reverse):
            task.cancel()
        local_writer.close()
        slot.writer.close()
        await asyncio.gather(local_writer.wait_closed(), slot.writer.wait_closed(), return_exceptions=True)
        slot.done.set()


async def handle_local(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    slots: asyncio.Queue[RelaySlot],
) -> None:
    try:
        slot = await asyncio.wait_for(slots.get(), timeout=5)
    except asyncio.TimeoutError:
        writer.close()
        await writer.wait_closed()
        return
    await bridge(reader, writer, slot)


async def handle_channel(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    slots: asyncio.Queue[RelaySlot],
    allowed_host: str,
) -> None:
    remote = writer.get_extra_info("peername")
    if not remote or remote[0] != allowed_host:
        writer.close()
        await writer.wait_closed()
        return
    try:
        if await reader.readexactly(len(CHANNEL_HELLO)) != CHANNEL_HELLO:
            raise ConnectionError("invalid relay channel")
        slot = RelaySlot(reader, writer, asyncio.Event(), asyncio.Event())
        await slots.put(slot)
        await slot.assigned.wait()
        await slot.done.wait()
    except (ConnectionError, asyncio.IncompleteReadError, asyncio.CancelledError):
        writer.close()
        await writer.wait_closed()


async def run(args: argparse.Namespace) -> None:
    allowed_host = str(ipaddress.ip_address(args.windows_address))
    slots: asyncio.Queue[RelaySlot] = asyncio.Queue(maxsize=args.channels)
    local_server = await asyncio.start_server(
        lambda reader, writer: handle_local(reader, writer, slots),
        "127.0.0.1",
        args.local_port,
    )
    channel_server = await asyncio.start_server(
        lambda reader, writer: handle_channel(reader, writer, slots, allowed_host),
        args.listen_host,
        args.channel_port,
    )
    print(
        f"WSL CDP reverse relay ready: local=127.0.0.1:{args.local_port} "
        f"channel={args.listen_host}:{args.channel_port} windows={allowed_host}",
        flush=True,
    )
    async with local_server, channel_server:
        await asyncio.gather(local_server.serve_forever(), channel_server.serve_forever())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen-host", required=True)
    parser.add_argument("--windows-address", default="172.19.0.1")
    parser.add_argument("--local-port", type=int, default=19222)
    parser.add_argument("--channel-port", type=int, default=19223)
    parser.add_argument("--channels", type=int, default=12)
    args = parser.parse_args()
    if args.local_port != 19222 or args.channel_port != 19223:
        parser.error("the qualification relay ports are fixed")
    asyncio.run(run(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
