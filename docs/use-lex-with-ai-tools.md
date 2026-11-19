# Use Lex with AI tools

Lex can also talk to other programs, not just to you. Add `--json` (or `-json`) to almost any Lex command and it prints its answer in a form that computers read easily. That makes it a good fit for AI assistants, scripts, and spreadsheets.

## What is JSON?

JSON is a plain-text way to write down information so a computer can read it without guessing. Every piece of information has a label. The normal Lex screen is made for your eyes, with colours, boxes, and menus. `--json` output is made for programs: one line of labelled text, no colours, no boxes, no menus, and nothing to press. The verse is always under the label `text`, the reference under `ref`, the book under `book`, and so on.

`--json` never asks you a question and never changes your saved Bible, theme, or history, so it is safe to run again and again from a script.

## Try it

```sh
lex --json John 3:16 | jq .
```

That prints the one-line answer spread out so it is easy to read (the `jq .` part does the spreading; see the next section). This is the real output from Lex 2.6.9:

```json
{
  "schema_version": 1,
  "lex_version": "2.6.9",
  "command": "read",
  "edition": "esv",
  "edition_name": "English Standard Version",
  "query": "John 3:16",
  "passages": [
    {
      "query": "John 3:16",
      "ref": "John 3:16",
      "book": "John",
      "chapter": 3,
      "verse_start": 16,
      "verse_end": 16,
      "verses": [
        {
          "ref": "John 3:16",
          "key": "esv:John:3:16",
          "book": "John",
          "chapter": 3,
          "verse": 16,
          "text": "“For God so loved the world, that he gave his only Son, that whoever believes in him should not perish but have eternal life."
        }
      ]
    }
  ],
  "not_found": []
}
```

Everything about the answer is labelled: which Bible was used (`edition`), the passage, and each verse with its book, chapter, number, and `text`. Verses you asked for that Lex could not find are listed under `not_found`.

## Pick out just what you want with jq

[jq](https://jqlang.org) is a free tool that picks pieces out of JSON. The `|` symbol (a "pipe") hands the output of one command to the next one. Install jq with your package manager (for example `brew install jq` on a Mac or `sudo apt install jq` on Ubuntu).

```sh
# Just the words of the verse
lex --json John 3:16 | jq -r '.passages[0].verses[0].text'
```

Output:

```text
“For God so loved the world, that he gave his only Son, that whoever believes in him should not perish but have eternal life.
```

```sh
# A search, one result per line: reference and text
lex --json search covenant -nt --limit 3 | jq -r '.results[] | "\(.ref): \(.text)"'
```

Output:

```text
Hebrews 7:22: This makes Jesus the guarantor of a better covenant.
Hebrews 9:18: Therefore not even the first covenant was inaugurated without blood.
Hebrews 9:15: Therefore he is the mediator of a new covenant, so that those who are called may receive the promised eternal inheritance, since a death has occurred that redeems them from the transgressions committed under the first covenant.
```

```sh
# How many matches in all, and which verses are on this page
lex --json search covenant -nt --limit 2 | jq -c '{total, page_count, refs: [.results[].ref]}'
```

Output:

```text
{"total":32,"page_count":16,"refs":["Hebrews 7:22","Hebrews 9:18"]}
```

A search answer looks like this (the long list of New Testament books under `scope` is left out here with `jq 'del(.scope.books)'`; everything else is exactly what Lex printed):

```json
{
  "schema_version": 1,
  "lex_version": "2.6.9",
  "command": "search",
  "edition": "esv",
  "edition_name": "English Standard Version",
  "query": "covenant",
  "effective_query": "covenant",
  "corrections": [],
  "mode": "term",
  "scope": {
    "label": "nt"
  },
  "page": 1,
  "limit": 2,
  "page_count": 16,
  "total": 32,
  "results": [
    {
      "rank": 1,
      "ref": "Hebrews 7:22",
      "key": "esv:Hebrews:7:22",
      "book": "Hebrews",
      "chapter": 7,
      "verse": 22,
      "text": "This makes Jesus the guarantor of a better covenant."
    },
    {
      "rank": 2,
      "ref": "Hebrews 9:18",
      "key": "esv:Hebrews:9:18",
      "book": "Hebrews",
      "chapter": 9,
      "verse": 18,
      "text": "Therefore not even the first covenant was inaugurated without blood."
    }
  ]
}
```

Word studies work the same way. This picks the main details from a Strong's entry (`lex --json strongs G3056 | jq '.entries[0] | {number,language,lemma,pronunciation,brief}'`):

```json
{
  "number": "G3056",
  "language": "greek",
  "lemma": "λόγος",
  "pronunciation": "log'-os",
  "brief": "something said (including the thought); by implication, a topic (subject of discourse), also reasoning (the mental faculty) or motive; by extension, a computation; specially, (with the article in John) the Divine Expression (i.e. Christ)"
}
```

The full entry also has `brief_refs`, `definition`, and `usage` (the verses where the word appears).

## Let an AI assistant use Lex

Any AI tool that can run commands for you can use Lex: coding assistants such as Cursor or Claude Code, ChatGPT or Claude tools that have a "run a command" or terminal option, and local models (for example through Ollama or LM Studio) inside an agent app that can run commands. There is nothing to install on the AI side and no key to paste in. Lex is just a command it runs, and Lex itself needs no internet.

The simplest way is to tell the assistant how to use it. Paste something like this into its instructions (or just into the chat):

```text
You can look up Scripture with the `lex` command on this computer. Always add
--json so you get structured output. Examples:
  lex --json John 3:16                  read a verse
  lex --json -B kjv John 3:16           read it in the King James Version
  lex --json search "kingdom of god"    search the Bible
  lex --json strongs G3056              look up a Greek or Hebrew word
  lex --json study John 1:1             original-language study data
Read the "text" fields and quote them exactly. If a command fails, the error
is JSON on stderr with a "code" and a "hint"; fix the command and try again.
```

Why bother? The assistant gets the real text from your own Bible data, with the book, chapter, and verse labelled, instead of quoting from memory.

## Good to know

- `--json` works with reading (`lex --json Romans 8:28`), `study`, `strongs`, `web`, `search`, `define`, `commentary`, `naves` / `topic`, `creed`, and `history`.
- Pick a Bible for one command with `-B` (`lex --json -B dra John 3:16`). The answer's `edition` field says which one was used. `-v` (which changes your saved Bible) is refused in JSON mode.
- If something goes wrong, the error is printed to stderr as JSON and Lex exits with a number: `2` for a mistake in the command, `3` for "not found", and `4` for missing data. Success is `0`. For example, `lex --json Nowhere 9:9` exits with `3` and prints:

```json
{
  "schema_version": 1,
  "lex_version": "2.6.9",
  "error": {
    "code": "not_found",
    "message": "No verse or chapter found for: Nowhere 9:9",
    "hint": "Check the reference, or use `lex --json search <terms>` for words and `lex --json strongs <number>` for Strong's."
  }
}
```

- The full list of fields for every command is in the [JSON output reference](https://github.com/elcafe7/lex/blob/main/docs/json-output.md). New fields can be added in version 1 of the format, but existing ones will not be renamed or removed without bumping `schema_version`.
- Want a clean, no-colour version for people instead? `lex --plain study John 1:1` prints the normal output as plain text.
