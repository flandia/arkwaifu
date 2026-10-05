"""Compare service SQL with a Git revision on a read-only archive; stdlib only."""

import argparse
import hashlib
import json
import math
import re
import sqlite3
import statistics
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CASES = [
    ("search", ("Rhodes", "EN")),
    ("search", ("zzzznotfound", "EN")),
    ("collection_story_references", ("CN", "section:setid_mainline_0_1")),
    (
        "collection_story_narrative_media_references",
        ("CN", "section:setid_mainline_0_1"),
    ),
    ("archive_group_references", ("CN", "events")),
    ("orphan_narrative_image_assets", ("CN",)),
    ("orphan_narrative_media_assets", ("CN",)),
]


def queries(source):
    return {
        name: re.search(
            r"^  let " + name + r" =.*?\{\|(.*?)\|\}", source, re.MULTILINE | re.DOTALL
        )[1]
        for name, _ in CASES
    }


def percentiles(values):
    ordered = sorted(values)
    return {
        f"p{p}_ms": round(ordered[math.ceil(len(ordered) * p / 100) - 1], 2)
        for p in (50, 95, 99)
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--requests", type=int, default=46)
    parser.add_argument("--waves", type=int, default=2)
    parser.add_argument("--samples", type=int, default=7)
    args = parser.parse_args()
    if min(args.workers, args.requests, args.waves, args.samples) <= 0:
        parser.error("workers, requests, waves and samples must be positive")
    root = Path(__file__).resolve().parents[3]
    source_path = "apps/service/lib/database.ml"
    revision = subprocess.check_output(
        ["git", "rev-parse", "--verify", args.baseline_ref + "^{commit}"],
        cwd=root,
        text=True,
    ).strip()
    before = queries(
        subprocess.check_output(
            ["git", "show", revision + ":" + source_path], cwd=root, encoding="utf-8"
        )
    )
    after = queries((root / source_path).read_text(encoding="utf-8"))
    uri = args.database.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    result = {
        "baseline_ref": revision,
        "sqlite_version": sqlite3.sqlite_version,
        "database_bytes": args.database.stat().st_size,
        "versions": connection.execute(
            "SELECT * FROM unit_versions ORDER BY unit"
        ).fetchall(),
        "rows": {
            table: connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
            for table in (
                "stories",
                "search_entries",
                "narrative_image_assets",
                "story_narrative_image_references",
            )
        },
        "workers": args.workers,
        "requests_per_wave": args.requests,
        "serial": [],
        "waves": [],
    }
    expected = {}
    for name, parameters in CASES:
        rows = connection.execute(before[name], parameters).fetchall()
        assert rows == connection.execute(after[name], parameters).fetchall(), (
            name,
            parameters,
        )
        expected[(name, parameters)] = hashlib.sha256(repr(rows).encode()).hexdigest()
        timings = {"before": [], "after": []}
        for _ in range(args.samples):
            for label, statements in (("before", before), ("after", after)):
                started = time.perf_counter()
                connection.execute(statements[name], parameters).fetchall()
                timings[label].append((time.perf_counter() - started) * 1000)
        result["serial"].append(
            {
                "query": name,
                "parameters": parameters,
                "rows": len(rows),
                "median_ms": {
                    label: round(statistics.median(values), 2)
                    for label, values in timings.items()
                },
                "plans": {
                    label: [
                        row[3]
                        for row in connection.execute(
                            "EXPLAIN QUERY PLAN " + statements[name], parameters
                        )
                    ]
                    for label, statements in (("before", before), ("after", after))
                },
            }
        )
    connection.close()

    def wave(statements):
        local = threading.local()
        connections = []

        def initialize():
            # Each worker owns its connection; the caller closes it after joining.
            local.connection = sqlite3.connect(uri, uri=True, check_same_thread=False)
            connections.append(local.connection)

        def execute(case, submitted):
            name, parameters = case
            started = time.perf_counter()
            rows = local.connection.execute(statements[name], parameters).fetchall()
            finished = time.perf_counter()
            assert hashlib.sha256(repr(rows).encode()).hexdigest() == expected[case], (
                case
            )
            return (
                (started - submitted) * 1000,
                (finished - started) * 1000,
                (finished - submitted) * 1000,
            )

        try:
            with ThreadPoolExecutor(
                max_workers=args.workers, initializer=initialize
            ) as executor:
                futures = [
                    executor.submit(
                        execute, CASES[index % len(CASES)], time.perf_counter()
                    )
                    for index in range(args.requests)
                ]
                samples = [future.result() for future in futures]
        finally:
            for database in connections:
                database.close()
        return {
            label: percentiles(sample[index] for sample in samples)
            for index, label in enumerate(("queue", "execution", "total"))
        }

    for number in range(args.waves):
        # Alternate order to reduce the advantage of running second.
        variants = [("before", before), ("after", after)]
        if number % 2:
            variants.reverse()
        for label, statements in variants:
            result["waves"].append(
                {"wave": number + 1, "variant": label, **wave(statements)}
            )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
