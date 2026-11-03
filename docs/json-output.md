# `lex --json` — machine-readable output (schema v1)

Status: draft for review (issue #16).

`--json` gives scripts and AI agents a stable, parseable result instead of the
Rich terminal UI. Put it anywhere before `--`:

```sh
lex --json John 3:16
lex --json -B kjv study Romans 1:1
lex strongs G3056 --limit 5 --json
```

## Guarantees

- **One JSON document on stdout**, compact, single line, UTF-8 (`ensure_ascii` off), ending in `\n`.
  Nothing else is written to stdout: no colour, no panels, no box characters.
- **Never interactive.** No prompts, pagers, "press Enter" or numbered menus, even on a TTY.
  stdin is never read.
- **No state changes.** `--json` never writes `~/.lex_config.json` (sticky Bible, theme)
  and does not record history.
- **`-B <edition>` is a one-command override**, exactly as in the UI.
- **`-v` / `lex version` / `lex bible` are refused** (`sticky_default_in_json`), because they
  change the saved default. Use `-B`.
- **Errors go to stderr as one JSON object** and the process exits nonzero (see below).
  stdout is empty on error.
- The npm launcher (`@n8te_/lex-cli`) stays quiet in JSON mode: no "latest release" or
  "downloading" lines, and first-run install output is suppressed. Launcher failures are
  reported as `{"schema_version":1,"error":{"code":"launcher",...}}` with exit 4.
- Theme flags (`-light`, `-dark`, …) are accepted and ignored.

## Envelope

Every success object starts with:

| field | type | notes |
|---|---|---|
| `schema_version` | int | `1`. Bumped only on breaking changes; new fields may be added in v1. |
| `lex_version` | string | e.g. `"2.6.6"` |
| `command` | string | `read`, `study`, `strongs`, `strongs_search`, `web`, `search`, `define`, `commentary`, `naves`, `creed`, `creed_list`, `creed_matches`, `creed_search`, `history` |
| `edition` | string | edition id actually used (`esv`, `kjv`, `gen`, …) |
| `edition_name` | string | display name |

### Verse object

Used everywhere a verse appears:

```json
{"ref":"John 3:16","key":"esv:John:3:16","book":"John","chapter":3,"verse":16,"text":"..."}
```

`book` uses the edition's own book name from the data (e.g. `Psalm` vs `Psalms`).
`key` is `edition:Book:chapter:verse` and is stable for joining results.

## Commands

### `read` — `lex --json <reference>[; <reference>…]`

```json
{ ...envelope, "query":"John 3:16-18; Psalm 117",
  "passages":[{"query":"John 3:16-18","ref":"John 3:16-18","book":"John","chapter":3,
               "verse_start":16,"verse_end":18,"verses":[<verse>, ...]}],
  "not_found":["Nowhere 9:9"] }
```

Whole chapters have `verse_start`/`verse_end` set to the chapter's range. Exit 3 only if
*every* reference failed; partial misses are listed in `not_found`.

### `study` — `lex --json study <reference>` (also `<reference> -i`)

```json
{ ...envelope, "query":"John 1:1",
  "verses":[{ <verse>,
    "source":{"base":"ESV interlinear","source_key":"esv:John:1:1",
              "confidence":"direct","warning":null,"language":"Greek"},
    "source_text":"Ἐν ἀρχῇ ἦν ὁ λόγος…","source_translit":"En archē ēn ho logos…",
    "tokens":[{"position":1,"word":"In","strongs":["G1722"],"gloss":null,"lemma":"ἐν",
               "lemma_translit":"en","surface":"Ἐν","translit":"En","morph":"P- --------",
               "source_order":0,"confidence":"direct"}]}],
  "not_found":[] }
```

- `strongs` is always a **list** (a token can carry several numbers, or none).
- `confidence`: `direct` (ESV interlinear), `proxy` (another English edition mapped onto the
  ESV interlinear, e.g. `-B gen`), `variant/proxy`, or `untagged` for tokens with no number.
- `source.warning` carries the same caveat the UI shows for proxy editions.
- `-B lxx`: tokens come from the parsed LXX dataset (`lxx.db`). `confidence` is `direct` when the
  token carries a Strong's number, `candidate` when only a lemma→Strong's mapping exists (then
  `candidate_strongs` and `candidate_confidence` are set), else `untagged`. Extra token fields:
  `pos`, `dependency`, `head`. `source.warning` describes coverage.
- `-B vulg`: each Latin word is matched to a `latin.db` headword by spelling (`confidence`
  `lexicon`, `lemma` = headword, `gloss` = definition, `pos`); `strongs` is always `[]`.
- The release data ships LXX/Vulgate *reading* text but not these study sets; without them
  study returns exit 4 `data_missing`.

### `strongs` — `lex --json strongs <G/H number>` (also bare `g26`)

```json
{ ...envelope, "query":"G26", "match":"number",
  "entries":[{"number":"G26","language":"greek","lemma":"ἀγάπη","pronunciation":"ag-ah'-pay",
    "brief":"love, i.e. affection…","brief_refs":[],
    "definition":{"text":"ἀγάπη, -ης, ἡ [in LXX for …","source":"Abbott-Smith"},
    "usage":{"index":"esv-interlinear","indexed":true,"projected_to":null,
             "total":106,"page":1,"limit":8,"page_count":14,"all":false,
             "verses":[{ <verse>, "source_key":"esv:Matthew:24:12","token_count":1 }],
             "note":null}}] }
```

- `brief` is plain text. Source entries stored as JSON fragments (e.g. G5594) are cleaned:
  cross-reference gaps are filled with the referenced numbers, and those numbers are also
  listed in `brief_refs`.
- `definition` is `null` when the extended lexicon has no entry. Text is plain (tags removed).
- `usage` comes from the ESV interlinear index only. `indexed:false` means the number does
  not occur in that index; `total:0` then is **not** proof the word is absent from the
  chosen edition (e.g. KJV-only tagging). `projected_to` names the `-B` edition when the
  verses were shown in another edition; `note` explains gaps.
- Paging: `--page N`, `--limit N` (default 8), `--all`.

### `strongs_search` — `lex --json strongs <english word>`

```json
{ ...envelope, "query":"love", "match":"english",
  "results":[{"number":"G25","language":"greek","lemma":"ἀγαπάω","pronunciation":"ag-ap-ah'-o",
              "matched":"love","brief":"to love (in a social or moral sense)","brief_refs":[]}] }
```

### `web` — `lex --json web <reference>`

```json
{ ...envelope, "query":"John 3:16", "verse":<verse>, "source":"openbible-tsk", "limit":12,
  "cross_references":[{"rank":1, <verse fields>, "tsk_ref":"Rom.5.8","votes":957}] }
```

`--limit N` (default 12, max 100).

### `search` — `lex --json search <terms> [scope flags]`

```json
{ ...envelope, "query":"grace", "effective_query":"grace", "corrections":[],
  "mode":"term", "scope":{"label":"nt","books":["Matthew", "..."]},
  "page":1, "limit":10, "page_count":12, "total":116,
  "results":[{"rank":1, <verse fields>}] }
```

- `corrections` lists spelling fixes applied (`{"from":"grase","to":"grace"}`);
  `effective_query` is what was searched.
- `scope` is `null` for the whole Bible; otherwise the scope flag (`-nt`, `-ot`, `-gospels`,
  a book…) and the books searched.
- `--page N`, `--limit N` (default 10). No results is exit 3 `not_found`.

### `define` — `lex --json define <term>` (also `-d <term>`)

```json
{ ...envelope, "query":"grace",
  "dictionary":[{"topic":"Grace","source":"Easton's Bible Dictionary","match":"exact",
                 "text":"Grace — (1.) Of form or person…","markdown":"…"}],
  "encyclopedia":[ ...same shape... ] }
```

Up to 3 per source. `match` is `exact`, `prefix` or `fulltext`. `text` is the Markdown with
emphasis/heading markers removed; `markdown` is the source.

### `commentary` — `lex --json commentary <reference>`

```json
{ ...envelope, "query":"John 3:16", "ref":"John 3:16", "book":"John", "chapter":3, "verse":16,
  "sections":[{"commentator":"Matthew Henry","source":"Matthew Henry's Commentary…",
               "title":"Christ's Interview with Nicodemus","verse_start":1,"verse_end":21,
               "text":"…","markdown":"…"}] }
```

A chapter reference (`verse: null`) returns every section in the chapter. Coverage follows the
installed commentary data (no match → exit 3).

### `naves` / `topic` — `lex --json naves <subject or reference>`

```json
{ ...envelope, "query":"prayer", "match":"exact",
  "topics":[{"subject":"PRAYER","entry":"-MISCELLANY…\n     -Daily…","refs":["PSA 5:3", "..."]}] }
```

`match` is `exact`, `substring` (up to 50) or `fulltext` (up to 20). `entry` keeps Nave's
indentation; `refs` are the references found in it, as written. A verse reference with no
subject match returns `{"match":"verse","verse":<verse fields>,"subjects":[...]}`.

### `creed` — `lex --json creed [<name or text>]` (also `-c`)

- No query → `command:"creed_list"`, `documents:[{id, topic, source, tradition, date, section_count}]`.
- One matching document → `command:"creed"`, `document:{topic, source, tradition, date,
  description, note, section_count, sections:[{title, text, markdown, proofs[], original}]}`.
  `original` is `{language, text}` when Lex has the original-language text, else `null`.
- Several documents → `command:"creed_matches"`, `matches:[{topic, source, tradition, section_count}]`.
- No title match → full-text: `command:"creed_search"`, `results:[{topic, title, source, text, proofs[]}]` (up to 8).

### `history` — `lex --json history [--limit N]`

Read-only: `items:[{ts, edition, command}]`, newest first (default 10). `history clear` /
`--clear` are refused in JSON mode.

## Errors

stderr, one line:

```json
{"schema_version":1,"lex_version":"2.6.6","error":{"code":"not_found","message":"...","hint":"..."}}
```

`hint` is optional; `unknown_edition` also includes `available` (edition ids) and `unsupported_in_json` includes `supported` (commands).

| exit | `code` | when |
|---|---|---|
| 1 | `internal` | unexpected exception (message only, no traceback) |
| 2 | `usage` | bad/missing arguments, bare flag (`-B` with no edition) |
| 2 | `sticky_default_in_json` | `-v`, `lex version`, `lex bible` |
| 2 | `unsupported_in_json` | command without a JSON schema yet (below) |
| 2 | `unknown_edition` | `-B xyz` |
| 2 | `unsupported_edition` | `study` on an edition with no study route |
| 3 | `not_found` | reference, Strong's number or search with no result |
| 4 | `data_missing` / `edition_not_installed` | runtime data not present |
| 4 | `launcher` | npm launcher could not install/start Lex |

## Not yet in JSON mode (`unsupported_in_json`)

`manuscript`, `export`, `help`/`commands`, `update`, `--credits`,
`words` (Geneva/KJV word tags, pending the geneva-word branch), `--next`/`--prev`. These fail fast rather than falling back to terminal output.

## `--plain`

`lex --plain <anything>` runs the normal command and prints its output as plain text: no
ANSI codes, no panel/table borders, no prompts, pagers or animation. Unlike `--json` it is
not a schema and may change between releases; settings behave as without the flag
(`-v` stays sticky). If both are given, `--json` wins.

## Planned

- `words` → `tokens[{word, strongs[], confidence}]` from the word-tag tier.
- Per-edition Strong's usage index (KJV/Geneva), so `usage.total` is edition-correct.
