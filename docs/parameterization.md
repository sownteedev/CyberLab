# Bounded Seed Parameterization

Development source supports typed `parameters` and three `parameterizations`
operations. These are CyberLab declarations, not an importer for Labtainer's
`parameter.config`, nor a claim of bit-for-bit seed compatibility.

```yaml
parameterizations:
  - id: random-port
    operation: rand_replace
    node: client
    path: config.txt
    token: PORT
    lower: 1000
    upper: 1010
    step: 2
  - id: generated-key
    operation: hash_create
    node: client
    path: exercises/key.txt
    value: "{{param:suffix}}"
```

## Behavior

- `rand_replace` replaces every non-overlapping token occurrence in one seeded
  UTF-8 file. The value is `lower + k * step`, within the inclusive range.
  The value is deterministic for the Session seed and operation ID. This is not
  a cryptographic random generator or a unique-address allocator.
- `hash_replace` substitutes a token with a lowercase MD5 digest.
- `hash_create` creates/overwrites one seeded file with that digest, without a
  trailing newline. It never replaces a directory and requires all directory
  parents to exist in the seed. It does not provision arbitrary system paths.
- The effective seed is the authored master seed (or empty string), `:`, and
  the Session ID. Hash input is that effective seed, `:`, and the declared value.
  Equal inputs in two hash operations produce equal hashes within a Session.
  MD5 is used for exercise compatibility, not credential security.
- Operations run in declaration order. Typed parameter substitution is a single
  pass before operations; a supplied value resembling a parameter token is
  literal input, not recursively evaluated. Reset preserves the Session's
  resolved seed data; saved/resumed practice preserves it across daemon restarts.

## Validation and bounds

The engine validates operations independently of the JSON/YAML loader. Unknown
operators/nodes, duplicate IDs, unsafe paths, missing tokens, non-UTF-8 targets,
directory replacement and invalid integer ranges fail before runtime start.
There are at most 64 operations; token text is at most 128 UTF-8 bytes and hash
input text at most 1024 bytes. Random fields are integers in 0..2147483647,
with a positive step no larger than the range's cardinality.

Initial assets, typed substitutions and generated files share the existing
1 MiB / 128 entry Lab seed budget. Replacement growth is calculated before
allocating expanded content; entries across nodes count toward the same budget.
No operation reads host paths, writes the catalog or executes scripts.

Studio keeps operation-specific fields separate when changing operation type.
Node renames update operations; referenced nodes cannot be deleted. The new
`LabeditParameterOperations` component is separate from typed parameter forms.

## Remaining parity

Implemented in source: `RAND_REPLACE_UNIQUE`, `CLONE_REPLACE` with container clone
expansion, sequential `+CLONE` IP incrementation, multi-target operations,
generated operation values in goals, network parameterization validated against
default parameters, and Labtainer format import.
Still pending: real-Docker acceptance and deployment to the installed system runtime.

Tests use temporary fixture Labs and the memory runtime. Determinism, reset,
save/restart/resume, malformed direct models, directory protection and aggregate
quotas are covered by `tests/test_parameterization.py`; shared API round trips
are in `tests/test_labedit_integration.py`. Installed/real-Docker acceptance is
still a release gate.
