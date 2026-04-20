# Lex Licensing Notes

This is a practical project note, not legal advice.

## Recommendation

Use a split-license model:

- **Lex application code:** MIT License.
- **Bundled data:** keep each dataset under its original license/terms.
- **Redistribution package:** include this note plus the upstream license files and attribution notices.

This is safer than trying to apply one license to everything. The project combines permissive code, public-domain/reference material, Creative Commons data, and Bible translation text that may require explicit permission.

Run this command in Lex for a full runtime attribution table:

```bash
lex --credits
```

## Why MIT for Code

MIT is the best fit for the CLI source code because it is simple, permissive, and compatible with most downstream use. It should apply only to code written for Lex, not to third-party datasets.

## Data Credits and Terms

Known local sources include:

- **Bible text:** ESV via local bible-data/ESV-derived database. Bible translation text should be treated as permission/copyright-controlled and not relicensed by Lex.
- **Cross-references:** Treasury of Scripture Knowledge data via OpenBible-style cross-reference data. Verify upstream terms before redistribution.
- **Strong's data:** public-domain Strong's-style concordance/lexicon data, per project README.
- **OpenScriptures Strong's XHTML:** local `strongs/strongs-dictionary.xhtml` states GPL-3.0. Because local notes differ, verify the exact Strong's source chain before public redistribution.
- **STEPBible:** CC BY 4.0; credit "STEP Bible" and link/reference STEPBible.org.
- **UBS Open License resources:** CC BY-SA 4.0; preserve attribution and ShareAlike obligations for adapted UBS material.
- **Bible Geocoding Data:** CC BY 4.0, based on local `Bible-Geocoding-Data/license.txt`.
- **Easton's Bible Dictionary:** public-domain dictionary material.
- **ISBE encyclopedia import:** public-domain International Standard Bible Encyclopedia OCR source, currently only Volume II (`Clement-Heresh`) imported.
- **Historical creeds/confessions:** local TheologAI historical document dataset; preserve source attribution and verify upstream terms before external redistribution.

## Practical Packaging Rule

If distributing Lex publicly:

1. Put application code under `LICENSE` with MIT text.
2. Add a `NOTICE` or `DATA_LICENSES.md` file listing every bundled dataset.
3. Ship original license files for STEPBible, UBS, Bible Geocoding, and bible-data.
4. Do not claim the ESV text is MIT/public domain.
5. If redistributing adapted UBS data, treat that adapted data package as CC BY-SA 4.0 unless counsel confirms a narrower obligation.
6. Keep generated databases labeled as compiled data with mixed source terms.

## Suggested Short Footer

```text
Code: MIT. Data: ESV, TSK/OpenBible, Strong's, STEPBible, UBS, Easton, ISBE,
TheologAI historical docs. Data remains under source terms.
```
