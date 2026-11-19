# Troubleshooting and FAQ

Quick fixes for the most common problems, and straight answers to common questions. If something is off, start by checking what your computer is running:

```sh
lex --version
type -a lex
```

## Something isn't working

| What you see | What to try |
|---|---|
| `lex` not found | Open a new terminal. For a Git install, check that `~/.local/bin` is on your `PATH` and run `./setup.sh` again. For an npm install, check that npm's global `bin` folder is on your `PATH` (`npm prefix -g` shows where). |
| `lex --version` prints something like `lex 2.6.4`, or `lex John 3:16` says it can't open `John` | Your computer already has an unrelated program called `lex` (the flex lexer) and it runs first. Type `type -a lex` to see, then open a new terminal after setup, or install a second name with `./setup.sh --alias lexb`. |
| Setup or first run fails | Check `python3 --version`: Lex needs Python 3.12 or newer. |
| Not sure which version you have | `lex --version` shows the Lex version. `lex --npm-version` shows the npm launcher's version. |
| "No reference result" | Try the full book name, such as `lex 1 Corinthians 13`. |
| Study mode says the interlinear data is not installed | Run `lex update` to download the data. |
| `lex update` says "Lex was not updated" on a Git clone | You have local changes to Lex's own files, and it lists them. Run `git stash` (or commit them), then `lex update` again. |
| An old update left `git pull` failing with "untracked working tree files would be overwritten" | An older Lex downloaded that file by itself. Delete the file git names (or move it aside), then run `git pull --ff-only`. After that, `lex update` handles this automatically: it moves any blocking file to `~/.lex_backups/` and carries on. |
| Output is messy in a log or CI job | Use `lex --plain ...` (no colour, boxes, or prompts) or `NO_COLOR=1`. Set `COLUMNS` to control the width; Lex honours it even when `TERM=dumb`. |
| A script or AI tool gets stuck or can't read the output | Use `lex --json ...`. It never prompts and prints one JSON document. Errors come back as JSON on stderr with exit code 2, 3, or 4. |
| A dictionary entry is missing | The local ISBE encyclopedia import is incomplete. It currently covers only Volume II (Clement to Heresh). |

## Frequently asked questions

**Does Lex need the internet?** Only to install and to update. Reading, searching, and studying all work offline.

**Is it free?** Yes. The code is MIT licensed. Bible texts and lexicons keep their own licenses; see the [licensing notes](https://github.com/elcafe7/lex/blob/main/docs/LICENSING.md).

**How do I update?** Type `lex update` (`lex --update` and `lex -update` are the same command). It updates Lex and its data together on every kind of install (Git clone, npm, or release download) and tells you the old and new version of each. On a Git clone it does the `git pull` and `./setup.sh` for you, and stops without changing anything if you have local edits to Lex's files.

**Which Bible versions are included?** Eight: ESV, KJV (1769 and 1611), NASB 1995, Geneva 1599, Douay-Rheims 1899, the Septuagint, and the Clementine Vulgate. See [Read a passage](read-a-passage.md).

**Where does Lex keep my settings and history?** In small files in your home folder: `~/.lex_config.json` (default Bible and theme), `~/.lex_history`, and `~/.lex_query_history`. `lex history --clear` clears the command history.

**Can I turn the colours off or switch to a light theme?** Yes. `NO_COLOR=1 lex John 3:16` turns colour off, and `lex -light` / `lex -dark` / `lex -auto` choose a theme.

**Is there a version for the browser?** Yes: [Lex Web](https://apocalypse.press/lex-web/).

**Found a bug or have an idea?** Please [open an issue](https://github.com/elcafe7/lex/issues). Security problems go through the [private reporting steps](https://github.com/elcafe7/lex/security/policy).
