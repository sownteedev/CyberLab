# Results and Goals Parity Slice

CyberLab keeps the Lab definition declarative and bounded. This slice brings in
the safe, workspace-scoped part of Labtainer's `results.config` model without
copying its timestamp archive, arbitrary executable hooks or host/system log
access.

## Supported result operators

Existing checks remain available: `exists`, `contains`, `equals`,
`line_contains`, `regex`, `size_less_than`, `size_equals`,
`line_count_equals` and `sha256_equals`.

The new operators are `md5_equals`, `string_count_equals` and `field_equals`.
The latter uses the following declaration:

```yaml
operator: field_equals
field_type: token       # token | parens | quotes | slash | group
field_id: 2             # 1-based; or ALL/LAST for non-group fields
line_type: starts_with  # line | starts_with | contains | regex | previous_starts_with
line_id: "VALUE"
expected: "42"
```

`group` uses a zero-based regex group number in `field_id` and requires
`line_type: regex`. Other field types use a positive one-based occurrence,
`ALL`, or `LAST`. `line_type: line` uses a one-based line number. A missing
selected line/field is a learner `FAIL`; invalid configuration, invalid regex,
or a timeout is an `ERROR`.

`previous_starts_with` selects the line before the **first** matching line.
If that first match is the first line, there is no selected value; later matches
are not substituted. Quote extraction preserves both single-quoted values and
empty strings. `ALL` returns the selected line, not a list of parsed fields.

All input is the declared workspace file captured for the current Session. Text
is bounded to 64 KiB. Regex and line-regex selectors run in the same isolated
worker with the existing one-second per-operation and five-second report
budget. Plain line selection does not launch a worker or consume that budget.
A regex group uses a single worker to select the first matching line and its
group. Worker JSON is bounded for escaped text as well as raw text; it is never
truncated into invalid JSON. Extracted `value` fields are included in the report
but never used to read an undeclared path. Studio displays a plain-text preview
limited to 512 characters and four lines; the stored report retains the value.

## Snapshot goal types

```yaml
assessment:
  results:
    - id: answer
      node: client
      path: answer.txt
      operator: field_equals
      field_type: token
      field_id: 2
      line_type: starts_with
      line_id: port
      expected: "42"
  goals:
    - id: equal-port
      type: compare
      operator: integer_equal
      result: answer
      expected: "42"
    - id: enough-checks
      type: count
      operator: count_greater
      results: [answer]
      threshold: 0
```

- `group` remains the default, combines a non-empty `results` list using `all`
  or `any`, and cannot carry comparison/count fields.
- `compare` uses `result` and exactly one of literal `expected` or another result
  ID in `other`. Dependencies are derived from these operands. An optional
  legacy `results` list must name exactly those same dependencies. Group `mode`
  and count `threshold` are not accepted on a comparison.
- String operators: `string_equal`, `string_diff`, `string_contains`,
  `string_start`, `string_end`. Integer operators: `integer_equal`,
  `integer_greater`, `integer_less`. Hash operators: `hash_equal` (MD5 for 32 hex,
  SHA-256 for 64 hex, case-insensitive compare of learner evidence against expected digest).
- `boolean` goal type: evaluates a safe, bounded boolean expression over earlier goals
  and results (e.g. `(goal1 and goal2) or not goal3`, `and_not`, `or_not`). Evaluated
  using 3-valued Kleene logic without code execution or Python eval.
- Integers are signed 64-bit decimal values, not floats, booleans, exponents or
  hexadecimal strings. Invalid authored literal expectations are rejected;
  substituted expectations are checked before starting a Session. Non-numeric
  learner evidence fails the criterion rather than being silently truncated.
- Comparisons use a captured value even when that Result's independent expected
  value did not pass. Missing selected evidence is a `FAIL`; failed capture or
  evaluation is an `ERROR`.
- `count_greater` counts passing Results in the current snapshot. If the known
  successes already exceed the threshold, it passes. If even all unknown Results
  passing cannot exceed it, it fails. Otherwise unknown/error Results produce
  `ERROR`, not an invented pass or fail. This is **not** Labtainer's count of
  timestamped event instances.

Normal Lab/Session metadata uses explicit public field lists. It excludes
expected values and selector arguments, which may contain resolved private
parameters. Checkwork goal reports do not echo expected values either. This
prevents accidental API disclosure, not examination-grade secrecy: local Lab
authors and declared workspace evidence are not an anti-cheating boundary.

Studio applies type changes atomically, removes incompatible fields and stores
visible defaults. Result renames update both comparison operands; referenced
Results cannot be removed until the author removes their references.

## Deliberately not supported yet

Labtainer also supports result streams with multiple timestamps, `LOG_TS`,
`LOG_RANGE`, `TIME_DELIM`, program stdin/stdout archives, and goal operators
such as `matchany`, `matchlast`, `matchacross`, `time_before`, `time_during`,
event-instance counting, and boolean expressions over temporal instances. CyberLab's
current Checkwork model captures one bounded workspace snapshot, so pretending
these are equivalent would be incorrect. They need a separate event/evidence
model before implementation.

`execute` goals, `pregrade.sh`, system logs, host mounts, privileged hooks and
arbitrary scripts are intentionally excluded by the CyberLab security policy.

## Verification

`tests/test_assessment_extractors.py` and `tests/test_assessment_goals.py` cover
selection boundaries, escaping, integer parsing, unknown counts and metadata
redaction. `tests/test_labedit_editor_transitions.py` drives rendered controls at
1024x700 and 1280x820, then validates every captured definition with the real
loader. `tests/test_labedit_integration.py` covers authoring, publication to a
temporary catalog, start, Checkwork, export and save/restart/resume through the
real CLI/private-D-Bus daemon with the memory runtime. No production catalog or
installed runtime is used by these checks; real-Docker acceptance is pending.
