#!/usr/bin/env bash
# Report which `lex` command your shell runs (issue #1).
#
# Many systems already have a `lex` on PATH: the flex lexical-analyzer
# generator (/usr/bin/lex on Linux and macOS). Whichever `lex` comes first in
# PATH wins. This lists every `lex` on PATH, labels each one, and says what to
# do if the first one is not Lex.
#
# Usage: scripts/check_lex_command.sh [--expect /path/to/lex] [--quiet-ok]
# Exit:  0 when `lex` runs Lex (or nothing named lex is on PATH yet),
#        1 when another program named lex comes first.

set -uo pipefail

expect=""
quiet_ok=0
while [ $# -gt 0 ]; do
    case "$1" in
        --expect) expect="${2:-}"; shift 2 ;;
        --quiet-ok) quiet_ok=1; shift ;;
        -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done

resolve() {
    # Portable realpath (macOS has no `realpath -e` by default).
    python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$1" 2>/dev/null || printf '%s\n' "$1"
}

is_lex_bible() {
    local path="$1" real
    real="$(resolve "$path")"
    if [ -n "$expect" ] && [ "$(resolve "$expect")" = "$real" ]; then
        return 0
    fi
    case "$real" in
        */lex-cli/bin/lex.js|*/lex.py) return 0 ;;
    esac
    # setup.sh writes a two-line wrapper that execs lex.py.
    if [ -f "$real" ] && [ "$(wc -c < "$real")" -lt 4096 ] && grep -q 'lex\.py' "$real" 2>/dev/null; then
        return 0
    fi
    return 1
}

is_flex() {
    local path="$1" real out
    real="$(resolve "$path")"
    case "$(basename "$real")" in
        flex|flex++) return 0 ;;
    esac
    # GNU flex invoked as `lex` prints "lex 2.6.4"; BSD lex prints "flex ...".
    if command -v timeout >/dev/null 2>&1; then
        out="$(timeout 2 "$path" --version 2>/dev/null | head -n 1)"
    else
        out="$("$path" --version 2>/dev/null </dev/null | head -n 1)"
    fi
    printf '%s\n' "$out" | grep -Eq '^(f?lex|flex) (version )?[0-9]'
}

label() {
    if is_lex_bible "$1"; then
        echo "Lex"
    elif is_flex "$1"; then
        echo "flex lexer, a C code generator"
    else
        echo "another program named lex"
    fi
}

# Every `lex` on PATH, in the order the shell searches them, without duplicates.
paths=()
IFS=':' read -r -a dirs <<< "${PATH:-}"
for dir in "${dirs[@]}"; do
    [ -n "$dir" ] || dir="."
    candidate="$dir/lex"
    if [ -f "$candidate" ] && [ -x "$candidate" ]; then
        dup=0
        for seen in "${paths[@]+"${paths[@]}"}"; do
            [ "$seen" = "$candidate" ] && dup=1
        done
        [ $dup -eq 0 ] && paths+=("$candidate")
    fi
done

if [ ${#paths[@]} -eq 0 ]; then
    [ $quiet_ok -eq 1 ] || echo "No command named lex is on PATH yet."
    exit 0
fi

first="${paths[0]}"
first_label="$(label "$first")"

if [ "$first_label" = "Lex" ]; then
    if [ $quiet_ok -eq 0 ] || [ ${#paths[@]} -gt 1 ]; then
        echo "OK: \`lex\` runs Lex ($first)."
        for other in "${paths[@]:1}"; do
            echo "  Also on PATH, but not used: $other ($(label "$other"))"
        done
    fi
    exit 0
fi

lex_dir=""
for p in "${paths[@]}"; do
    if is_lex_bible "$p"; then lex_dir="$(dirname "$p")"; break; fi
done
if [ -z "$lex_dir" ] && [ -n "$expect" ]; then
    lex_dir="$(dirname "$expect")"
fi

echo "WARNING: \`lex\` runs $first ($first_label), not Lex."
echo "  lex commands on PATH, first one wins:"
n=1
for p in "${paths[@]}"; do
    echo "    $n. $p ($(label "$p"))"
    n=$((n + 1))
done
echo "  Fix: put Lex's folder ahead of $(dirname "$first") in PATH, in your shell's startup file"
echo "  (~/.bashrc, ~/.zshrc, or ~/.config/fish/config.fish), then open a new terminal:"
if [ -n "$lex_dir" ]; then
    echo "    export PATH=\"$lex_dir:\$PATH\""
else
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
fi
echo "  (fish: fish_add_path ${lex_dir:-\$HOME/.local/bin})"
echo "  Or give Lex a second name that cannot clash: ./setup.sh --alias lexb  (then: lexb John 3:16)"
echo "  Check again any time with: type -a lex"
exit 1
