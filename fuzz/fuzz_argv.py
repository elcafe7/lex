#!/usr/bin/env python3
"""Atheris fuzz harness for Lex CLI argument handling (issue #36).

Targets the code every command line passes through before argparse:
- normalize_argv: one-dash/two-dash option aliases
- protect_search_scope_flags: hides `lex search grace -nt` scopes from argparse
- help_requested / json_mode_requested: flag detection before `--`
- LexAgent.parse_search_query_and_scope / parse_book_scope: search scopes

Each input must either return normally or raise nothing; any exception, or a
broken invariant (asserted below), is a crash and fails the fuzz job.

Run locally:
    pip install --require-hashes -r .github/requirements/fuzz-requirements.txt
    python fuzz/fuzz_argv.py fuzz/corpus/argv -max_total_time=60
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _lex_loader import load_lex  # noqa: E402

lex = load_lex()
PARSER = lex.build_arg_parser()
# parse_book_scope / parse_search_query_and_scope only use module tables, so a
# bare instance (no __init__, no database connections) is enough.
AGENT = object.__new__(lex.LexAgent)

MAX_TOKENS = 24


def split_input(data):
    """Turn raw bytes into an argv list: NUL-separated tokens."""
    text = data.decode("utf-8", errors="replace")
    return text.split("\x00")[:MAX_TOKENS]


def check_argv(argv):
    """Run the argv helpers and assert their invariants."""
    normalized = lex.normalize_argv(argv, PARSER)
    assert isinstance(normalized, list)
    assert len(normalized) == len(argv), (argv, normalized)
    # Normalizing twice changes nothing.
    assert lex.normalize_argv(normalized, PARSER) == normalized, (argv, normalized)
    # Nothing after an end-of-options marker is ever rewritten.
    if "--" in argv:
        idx = argv.index("--")
        assert normalized[idx:] == argv[idx:], (argv, normalized)
    # Non-option tokens pass through untouched.
    for before, after in zip(argv, normalized):
        if before == "--":
            break
        if not before.startswith("-"):
            assert before == after, (before, after)

    protected = lex.protect_search_scope_flags(list(normalized))
    assert len(protected) == len(normalized)

    assert isinstance(lex.help_requested(normalized), bool)
    assert isinstance(lex.json_mode_requested(normalized), bool)


def check_scope(query):
    """Parse a search query and its book scope; assert the result shape."""
    terms, scope = AGENT.parse_search_query_and_scope(query)
    assert isinstance(terms, str)
    if scope is not None:
        assert isinstance(scope["label"], str) and scope["label"]
        assert scope["books"], scope
        assert all(isinstance(book, str) and book for book in scope["books"]), scope
    for token in query.split():
        parsed = AGENT.parse_book_scope(token)
        assert parsed is None or parsed["books"], (token, parsed)


def test_one_input(data):
    argv = split_input(data)
    check_argv(argv)
    check_scope(" ".join(argv))


def main():
    import atheris

    atheris.instrument_all()
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
