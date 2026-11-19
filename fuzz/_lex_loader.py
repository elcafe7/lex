"""Shared helpers for the Atheris fuzz harnesses (issue #36).

Loads lex.py and scripts/safe_paths.py as modules without running the CLI,
so the harnesses exercise the real parsing and path-boundary code.
"""
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_module(name, relative_path):
    path = os.path.join(ROOT, relative_path)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_lex():
    return load_module("lex_under_fuzz", "lex.py")


def load_safe_paths():
    return load_module("safe_paths_under_fuzz", os.path.join("scripts", "safe_paths.py"))
