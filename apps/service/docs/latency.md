# Issue #53: SQL latency evidence

The query changes reduce time spent occupying the service's shared query
resources. Search now selects the requested locale before scanning story
text and looks up references only for matching stories. Collection and Archive
queries select their parent stories before resolving references. AnimeKV checks
use the existing `(category, asset_id)` index to bound the literal slash prefix.
The original substring predicate remains as the final check.

No schema change or new index is required. Orphan queries already use the asset
reference indexes; their SQL is unchanged. Search keeps its existing literal
substring matching, ranking, and 100-result limit, including one-character CJK
queries. These measurements do not establish a need for FTS.

The frontend aborts stale fetches when the query or locale changes or the search
page unmounts, and clears pending debounce timers. An aborted pending cache entry
can be retried immediately. This does not interrupt a SQLite statement already
running in a service worker; such statements finish with the reduced query work.

## Dataset and method

Measured locally on Windows on 2026-09-07 with Python's SQLite **3.45.3**. The
read-only cached generation was
`E:\arkwaifu\service-database\arkwaifu-560-0.sqlite3`, last written 2026-08-24,
with **537,645,056 bytes (512.7 MiB)** and schema version 2. It contains 15,453
stories, 97,161 search entries, 15,614 narrative images, and 347,612 story image
references across all five locales. This is an older local snapshot.

| Unit | Published resource version |
| --- | --- |
| artwork | `26-08-17-11-22-14_59d37d` |
| CN | `26-08-17-11-25-42_dbc172` |
| EN | `26-08-17-16-42-26_e34be5` |
| JP | `26-08-17-10-18-20_cb5177` |
| KR | `26-08-13-13-33-15_28ff85` |
| TW | `26-08-13-10-20-44_f1070a` |

The measurements used local revision `d9cc1fb782de5534ba6450b824743b526d7322f3`.
For reproduction, use published commit `2203d7729da3b59995abe1b5ba8d0e9e02a362ac`;
every profiled SQL statement is identical to the measured baseline. The profiler
extracts the exact SQL from that published revision and the current reader, opens the
archive with `mode=ro`, and verifies identical ordered result rows. It records
query plans and interleaves seven warm serial samples for each version.

| Query | Returned rows | Before median | After median |
| --- | ---: | ---: | ---: |
| EN search: `Rhodes` | 100 | 399.84 ms | 130.91 ms |
| EN search: `zzzznotfound` | 0 | 329.34 ms | 87.15 ms |
| CN section image references | 157 | 117.64 ms | 0.40 ms |
| CN section media references | 72 | 135.02 ms | 0.23 ms |
| CN Archive event references | 4,340 | 341.12 ms | 8.48 ms |
| CN orphan images | 2,597 | 13.74 ms | 13.76 ms |
| CN orphan media | 20,873 | 36.70 ms | 36.35 ms |

The section is `section:setid_mainline_0_1`. Before the changes, its reference
queries scanned all references in the locale, including when the requested
collection was empty. The updated plans use the collection/story indexes.
Search previously scanned stories and search entries across all locales; its
updated plans constrain both by locale. The AnimeKV subquery changes from a
category-only scan to a range lookup on the asset ID.

## Concurrent SQL simulation

Each wave submits **46 requests to four worker threads**, each with its own
read-only connection. The seven queries above repeat in table order, producing
14 searches, seven section image queries, seven section media queries, six
Archive queries, and six queries of each orphan kind. Two waves run in opposite
before/after order. Every concurrent result is checked against its baseline.

Times below include executor queue wait from submission until SQLite rows have
been fetched. Percentiles use nearest rank; P99 is the maximum of 46 samples.

| Wave | Version | Queue P95 | Total P95 | Total P99 |
| --- | --- | ---: | ---: | ---: |
| 1 | Before | 3,894.00 ms | 4,313.87 ms | 4,478.79 ms |
| 1 | After | 628.18 ms | 644.83 ms | 752.60 ms |
| 2 | Before | 3,843.65 ms | 4,246.43 ms | 4,437.58 ms |
| 2 | After | 628.99 ms | 650.35 ms | 751.80 ms |

This is a bounded SQL simulation, not native service acceptance testing. It
includes Python row fetching and result verification between worker tasks. It
does not reproduce Caqti pooling, multi-query HTTP handlers, Dream/Lwt scheduling,
OCaml JSON encoding, network transfer, client cancellation, database refresh,
or the production host's memory and disk limits. The OS file cache was warm;
connections start fresh for each concurrent wave. Two waves cannot characterize
production tail latency.

## Reproduce and verify the running service

From `apps/service/`, run the stdlib [SQL profiler](../scripts/profile_sql.py)
against a local published archive:

```powershell
python scripts/profile_sql.py E:/arkwaifu/service-database/arkwaifu-560-0.sqlite3 --baseline-ref 2203d7729da3b59995abe1b5ba8d0e9e02a362ac --workers 4 --requests 46 --waves 2 --samples 7 > D:/Cache/arkwaifu-issue53/sql-profile.json
```

The captured JSON is at that cache path for this local run; the database and
generated results are not repository artifacts. The profiler's default query
cases target this Arknights snapshot, so confirm the named collection exists
when using a different archive.

The native service could not run in this session: the opam executable returned
`Access denied`, the Docker daemon was unavailable, and local MinIO was stopped.
After the supported preview is running, use the
[HTTP latency probe](../scripts/probe_latency.py) to measure endpoint P95/P99,
`/health`, and `Server-Timing` under concurrency. Native tests and those HTTP
measurements remain necessary before claiming the deployed service meets its
latency budgets.
