# Submission pre-check, 2026-11-14 (image `junction-sorter:v1`)

Built from commit 777a15f (`aalto-humanoid/` unchanged since) on a Verda VM, upstream pinned at 36daf5b.
Same checks as the organisers' hand-in pre-check (upstream `SUBMISSION.md` §6.3).

| Check | Result |
|---|---|
| Platform | linux/amd64 |
| Size | 307 MB uncompressed (limit 40 GB), 290 MB as `docker save | gzip` |
| Image id | `sha256:1eb9d4b82c7c3f9fb4413d0a9c985bd876ed1c3b20188fb859b9f04837a1cf73` |
| `replay --synthetic 100 --container` | PASS: 887 commands/s (gate 27), p50 latency 6.8 ms, max 11.9 ms, 0 errors, startup 0.52 s (limit 120 s) |
| `runner --backend mock --container`, 3 episodes | 3/3 `done`, 0 clipped steps, 30.0 Hz, ~25 s per episode |
| `pytest tests/` inside the image | 56 passed |

Not done: the Isaac Sim rerun with `AALTO_DR=train` and 10 trials per task. The only free RTX on Verda was
`1RTXPRO6000.30V.CC` (confidential compute): CUDA works after `nvidia-smi conf-compute -srs 1`, but the driver
exposes no Vulkan in CC mode (`vkCreateInstance: ERROR_INCOMPATIBLE_DRIVER`), so Isaac cannot render. No L40S or
other RTX type had capacity.
