"""Measure concurrent GET latency against a running service; uses only stdlib."""

import argparse
import json
import math
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import urlopen


def percentiles(values):
    durations = sorted(values)
    return {
        "p50_ms": round(durations[math.ceil(len(durations) * 0.50) - 1], 2),
        "p95_ms": round(durations[math.ceil(len(durations) * 0.95) - 1], 2),
        "p99_ms": round(durations[math.ceil(len(durations) * 0.99) - 1], 2),
        "max_ms": round(durations[-1], 2),
    }


def summarize(samples):
    return {
        "requests": len(samples),
        "errors": sum(sample[2] != 200 for sample in samples),
        "statuses": dict(Counter(str(sample[2]) for sample in samples)),
        **percentiles(sample[1] for sample in samples),
        "server_timing_ms": {
            stage: percentiles(sample[3][stage] for sample in samples if stage in sample[3])
            for stage in ("pool", "db", "json")
            if any(stage in sample[3] for sample in samples)
        },
    }


def parse_timing(value):
    return {
        name: float(duration)
        for name, duration in re.findall(
            r"(?:^|,)\s*(pool|db|json);dur=([0-9]+(?:\.[0-9]+)?)(?=\s*(?:,|$))", value
        )
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", help="Service origin, e.g. http://127.0.0.1:5174")
    parser.add_argument("--concurrency", type=int, default=46)
    parser.add_argument("--rounds", type=int, default=50, help="Requests per path")
    parser.add_argument("--timeout", type=float, default=120, help="Seconds per request")
    parser.add_argument("--locale", choices=["CN", "EN", "JP", "KR", "TW"], default="EN")
    parser.add_argument(
        "--query", action="append", help="Search text; repeatable (default: Rhodes)"
    )
    parser.add_argument("--movement-id", help="Include this movement's detail in the mix")
    parser.add_argument("--path", action="append", help="Replace application mix; repeatable")
    parser.add_argument("--warmup", type=int, default=1, help="Untimed rounds; 0 skips warmup")
    parser.add_argument("--assert-budgets", action="store_true")
    parser.add_argument("--health-p95-ms", type=float, default=250)
    parser.add_argument("--app-p95-ms", type=float, default=2000)
    parser.add_argument("--app-p99-ms", type=float, default=5000)
    args = parser.parse_args()
    origin = urlsplit(args.base_url)
    if (
        origin.scheme not in ("http", "https")
        or not origin.netloc
        or origin.query
        or origin.fragment
    ):
        parser.error("base_url must be an HTTP(S) service URL without a query or fragment")
    if min(args.concurrency, args.rounds, args.timeout) <= 0 or args.warmup < 0:
        parser.error("concurrency, rounds and timeout must be positive; warmup must be nonnegative")
    prefix = f"/api/{args.locale}"
    paths = args.path or [
        *[f"{prefix}/search?q={quote(query, safe='')}" for query in (args.query or ["Rhodes"])],
        f"{prefix}/scores",
        f"{prefix}/orphans",
        f"{prefix}/archives",
        f"{prefix}/galleries",
    ]
    if args.movement_id:
        paths.append(f"{prefix}/scores/{quote(args.movement_id, safe='')}")
    if any(not path.startswith("/") or path.startswith("//") for path in paths):
        parser.error("each path must start with a single slash")
    paths = list(dict.fromkeys(["/health", *paths]))
    if len(paths) < 2:
        parser.error("include at least one application path")

    def request(path):
        started = time.perf_counter()
        timing = {}
        try:
            with urlopen(args.base_url.rstrip("/") + path, timeout=args.timeout) as response:
                response.read()
                status = response.status
                timing = parse_timing(response.headers.get("Server-Timing", ""))
        except HTTPError as error:
            status = error.code
            timing = parse_timing(error.headers.get("Server-Timing", ""))
            error.close()
        except (URLError, TimeoutError, OSError, HTTPException) as error:
            status = type(error).__name__
        return path, (time.perf_counter() - started) * 1000, status, timing

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        warmup = list(pool.map(request, paths * args.warmup))
        if any(sample[2] != 200 for sample in warmup):
            print(json.dumps({"warmup": warmup}, indent=2))
            return 1
        started = time.perf_counter()
        samples = list(pool.map(request, paths * args.rounds))
        elapsed = time.perf_counter() - started
    by_path = {
        path: summarize([sample for sample in samples if sample[0] == path]) for path in paths
    }
    app = summarize([sample for sample in samples if sample[0] != "/health"])
    failures = []
    if any(sample[2] != 200 for sample in samples):
        failures.append("HTTP or transport errors")
    if args.assert_budgets:
        if by_path["/health"]["p95_ms"] > args.health_p95_ms:
            failures.append("health P95 budget exceeded")
        if app["p95_ms"] > args.app_p95_ms:
            failures.append("application P95 budget exceeded")
        if app["p99_ms"] > args.app_p99_ms:
            failures.append("application P99 budget exceeded")
    print(
        json.dumps(
            {
                "base_url": args.base_url,
                "concurrency": args.concurrency,
                "warmup_rounds": args.warmup,
                "elapsed_seconds": round(elapsed, 3),
                "requests_per_second": round(len(samples) / elapsed, 2),
                "application": app,
                "paths": by_path,
                "failures": failures,
            },
            indent=2,
        )
    )
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
