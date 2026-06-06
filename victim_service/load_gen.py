"""Simple traffic generator for the victim frontend.

Run locally or from Cloud Shell to drive enough requests that Cloud Monitoring
sees a meaningful error/latency signal Faultline can detect.

Usage:
    python -m victim_service.load_gen --url https://<frontend-cloud-run>.run.app \\
                                       --rps 5 --duration 120
"""

from __future__ import annotations

import argparse
import asyncio
import time

import httpx


async def _worker(client: httpx.AsyncClient, url: str, stop_at: float, stats: dict) -> None:
    while time.monotonic() < stop_at:
        t0 = time.monotonic()
        try:
            r = await client.get(url, timeout=10.0)
            stats["count"] += 1
            stats["latency_total"] += time.monotonic() - t0
            if r.status_code >= 500:
                stats["errors"] += 1
        except Exception:
            stats["count"] += 1
            stats["errors"] += 1


async def _run(url: str, rps: int, duration: int) -> dict:
    stats = {"count": 0, "errors": 0, "latency_total": 0.0}
    stop_at = time.monotonic() + duration
    interval = 1.0 / max(rps, 1)
    async with httpx.AsyncClient() as client:
        tasks: list[asyncio.Task] = []
        next_at = time.monotonic()
        while time.monotonic() < stop_at:
            tasks.append(asyncio.create_task(_worker(client, url, next_at + 1.0, stats)))
            next_at += interval
            sleep_for = next_at - time.monotonic()
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
        await asyncio.gather(*tasks, return_exceptions=True)
    return stats


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True, help="frontend URL, e.g. https://x.run.app/")
    p.add_argument("--rps", type=int, default=2)
    p.add_argument("--duration", type=int, default=60, help="seconds")
    args = p.parse_args()

    stats = asyncio.run(_run(args.url, args.rps, args.duration))
    n = max(stats["count"], 1)
    print(
        f"sent={stats['count']} errors={stats['errors']} "
        f"avg_latency_ms={1000 * stats['latency_total'] / n:.1f}"
    )


if __name__ == "__main__":
    main()
