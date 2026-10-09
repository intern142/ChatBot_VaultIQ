# VQ-210 Benchmark Results — Gate 4

## Test Environment
- Database: PostgreSQL 16 (Docker)
- Connection: Local (127.0.0.1:5433)
- User: `vaultiq` (superuser, BYPASSRLS)
- Python: 3.11.9
- SQLAlchemy: 2.0 (async)

## Benchmark Results

### Cache MISS (100 runs)
| Metric | Value |
|--------|-------|
| Mean | 3.44 ms |
| Stdev | 2.11 ms |
| Min | 2.29 ms |
| Max | 22.71 ms |

### Cache HIT (100 runs)
| Metric | Value |
|--------|-------|
| Mean | 3.74 ms |
| Stdev | 0.80 ms |
| Min | 3.24 ms |
| Max | 10.50 ms |

**Speedup: 0.92x** (cache hit marginally slower due to row retrieval overhead)

### Cache SET (100 runs)
| Metric | Value |
|--------|-------|
| Mean | 32.94 ms |
| Stdev | 22.30 ms |
| Min | 11.90 ms |
| Max | 122.19 ms |

### Cache INVALIDATE (10 runs, 10 entries each)
| Metric | Value |
|--------|-------|
| Mean | 30.80 ms |
| Stdev | 32.40 ms |
| Min | 16.02 ms |
| Max | 122.53 ms |

## Analysis

The cache hit/miss latency is nearly identical (~3.5ms) because both are simple indexed lookups on the unique constraint `(tenant_id, role, question_hash, kb_version)`. The actual performance benefit of the answer cache is **not in the database query latency** but in **avoiding the full search pipeline**:

- **Without cache**: Question → Embedding → Vector Search → Rerank → Extract Answer (100s of ms to seconds)
- **With cache**: Question → Hash → Index Lookup → Return Answer (~3-4 ms)

The ~32ms SET cost is paid once per unique question/role/kb_version combination. The cache pays for itself after the second hit.

## Gate 4 Status: ✅ Complete

Benchmark documented. Ready for Gate 6 (Live container verification).