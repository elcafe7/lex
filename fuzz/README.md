# Fuzzing

[Atheris](https://github.com/google/atheris) (libFuzzer for Python) harnesses
for the code that handles untrusted input. They satisfy the OpenSSF Scorecard
Fuzzing check (issue #36) and run in `.github/workflows/fuzz.yml`.

| Harness | What it fuzzes | Invariants |
|---|---|---|
| `fuzz_argv.py` | `normalize_argv`, `protect_search_scope_flags`, `help_requested`, `json_mode_requested`, search scopes (`parse_book_scope`, `parse_search_query_and_scope`) | no exception; argv length kept; normalizing is idempotent; nothing after `--` and no non-option token is rewritten; any scope has a label and books |
| `fuzz_safe_paths.py` | `check_relative_part`, `safe_join`, `confine_path` (lex.py) and `safe_source_file` / `safe_source_dir` (scripts/safe_paths.py) | only `UnsafePathError` is raised; any returned path is inside the base directory, including through symlinks and a `base-evil` sibling |

Seed inputs live in `corpus/<target>/` (argv seeds are NUL-separated tokens).
`tests/test_fuzz_harness.py` replays them in the normal test suite, without
Atheris.

Run locally (Linux x86-64, Python 3.12+):

```bash
python3 -m venv .fuzz-venv
.fuzz-venv/bin/pip install --require-hashes --no-deps -r .github/requirements/fuzz-requirements.txt
cp -R fuzz/corpus/argv /tmp/corpus-argv
.fuzz-venv/bin/python fuzz/fuzz_argv.py /tmp/corpus-argv -max_total_time=60
```

A crash writes `crash-<sha1>` with the input; re-run the harness with that
file as its only argument to reproduce it. Add a minimised copy to the corpus
once fixed.
