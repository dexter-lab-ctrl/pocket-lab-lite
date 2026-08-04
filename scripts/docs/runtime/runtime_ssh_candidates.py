#!/usr/bin/env python3
"""Validate and rank operator-approved private SSH targets without guessing."""
from __future__ import annotations

import argparse
import ipaddress
import re
import sys
from typing import Iterable

TAILSCALE_NETWORK = ipaddress.ip_network("100.64.0.0/10")
PRIVATE_IPV4_NETWORKS = tuple(ipaddress.ip_network(value) for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
PRIVATE_IPV6_NETWORK = ipaddress.ip_network("fc00::/7")
TAILSCALE_DNS = re.compile(r"[a-z0-9-]+(?:\.[a-z0-9-]+)*\.ts\.net", re.I)
IPV4_PATTERN = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")


def is_safe_target(value: str) -> bool:
    candidate = value.strip().rstrip(".")
    if not candidate:
        return False
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError:
        return bool(TAILSCALE_DNS.fullmatch(candidate))
    if any((address.is_loopback, address.is_link_local, address.is_multicast, address.is_unspecified, address.is_reserved)):
        return False
    if address.version == 4:
        return address in TAILSCALE_NETWORK or any(address in network for network in PRIVATE_IPV4_NETWORKS)
    return address in PRIVATE_IPV6_NETWORK


def ranked_ipv4_candidates(text: str) -> list[str]:
    observed: set[ipaddress.IPv4Address] = set()
    for token in IPV4_PATTERN.findall(text):
        try:
            address = ipaddress.ip_address(token)
        except ValueError:
            continue
        if not isinstance(address, ipaddress.IPv4Address) or not is_safe_target(token):
            continue
        observed.add(address)
    return [
        str(address)
        for address in sorted(observed, key=lambda item: (0 if item in TAILSCALE_NETWORK else 1, int(item)))
    ]


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate-host")
    validate.add_argument("value")
    subparsers.add_parser("rank-candidates")
    args = parser.parse_args(argv)
    if args.command == "validate-host":
        return 0 if is_safe_target(args.value) else 1
    for value in ranked_ipv4_candidates(sys.stdin.read()):
        print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
