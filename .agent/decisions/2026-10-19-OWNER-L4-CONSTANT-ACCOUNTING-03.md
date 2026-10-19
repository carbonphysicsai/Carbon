# OWNER-L4-CONSTANT-ACCOUNTING-03: graph constants are counted in values

**Owner:** Ryan, 2026-10-19 ("count in numbers"), relayed to Launchpad by the Test Lead session the same day. It answers Martin's report that float64 constants were charged double against the cap.

**Decision:** the Level 4 constant cap counts constant **values**, not bytes.
- **The limit is unchanged.** The 16 KiB `constant_bytes` cap stays (OWNER-L4-VALUES-01). Every value is charged `graph.VALUE_BYTES` = 4 bytes whatever its dtype, so the cap is 4,096 values, the count it always allowed at float32. float64 is no longer charged double.
- **Identical constants still count once** (OWNER-L4-CONSTANT-ACCOUNTING-02).
- **Published kit inputs still don't count at all** (OWNER-L4-CONSTANT-ACCOUNTING-02, item 2).

This is accounting **v3** (`level4-constant-accounting-v3`).

**Versioning:** prospective.
- Verdicts recorded under v1 (raw bytes) or v2 (unique bytes) keep their meaning and are never re-measured.
- New verdicts record `constant_accounting` and carry, besides the earlier measurements:
  - `unique_constant_values`;
  - `constant_value_bytes`, which is what the cap reads.

**Boundary:** a value still carries at most one number. Narrow dtypes (int8, bfloat16) are now charged 4 bytes a value rather than their own size, so no dtype holds more numbers under the cap than float32 always could.

**Implementation:**
- `carbon/level4/graph.py`: `unique_constant_values` and `VALUE_BYTES`;
- `allowlist.MEASURED_AS["constant_bytes"] = "constant_value_bytes"`;
- the static-scatter registered bound in `lower_torch`;
- tests in `tests/cpu/test_level4_graph.py`.

No scientific, security, LIVE or economic authority follows from this file.
