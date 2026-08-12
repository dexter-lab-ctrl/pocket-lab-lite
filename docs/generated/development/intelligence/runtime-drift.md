---
title: "Runtime drift"
description: "Expected repository/runtime alignment without confusing drift with semantic parity or operational health."
generated: true
audience: development
confidence: generated
---

# Runtime drift

Configuration/runtime drift, semantic parity, and operational health are separate dimensions.

| Kind | Resource | Classification | Runtime | Expectation |
| --- | --- | --- | --- | --- |
| service | caddy | aligned | healthy | matched |
| service | core-supervisor | aligned | online | matched |
| service | lite-api | aligned | online | matched |
| service | nats | aligned | ready | matched |
| service | node-agent | aligned | online | matched |
| service | photoprism | aligned | online | matched |
| service | pm2 | aligned | ready | matched |
| service | proot-ubuntu | not-evaluated | unavailable | not-evaluated |
| service | sqlite | aligned | healthy | matched |
| service | tailscaled | aligned | ready | matched |
| service | worker | aligned | online | matched |
| route | api-lite | aligned | present | route-contract |
| route | photoprism | aligned | present | route-contract |
| route | pwa | aligned | present | route-contract |
| route | remote-access | aligned | present | route-contract |
| datastore | sqlite-control-plane | aligned | ok | schema-expectation |

## Semantic drift (independent)

| Domain | Parity | Mismatches |
| --- | --- | --- |
| apps | drift-detected | 2 |
| devices | verified-with-mapped-presentation | 0 |
| home | verified-with-mapped-presentation | 0 |
| identity | partial | 0 |
| recovery | drift-detected | 9 |
| rules | partial | 0 |
| security | verified-with-mapped-presentation | 0 |
