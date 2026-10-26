# LEGO Pick a Brick upload format

Verified on the official US storefront on 2026-10-25:
https://www.lego.com/en-us/pick-and-build/pick-a-brick

In **Upload List**, LEGO's **CSV Template** is a downloadable data URL whose decoded contents are:

```csv
elementId,quantity
300321,18
300121,999
```

The template uses CRLF line endings. These are examples only, not default pieces to put in a user's build. Element IDs encode both design and color. LDraw IDs, BrickLink IDs, and LEGO design IDs are not interchangeable with these IDs.

The current US uploader advertises 400 distinct pieces and a 5 MB file limit. Other locales can have different limits. This skill conservatively supports at most 200 distinct part/color combinations across its supported markets and a maximum of 999 of one element (or a lower live catalog limit). It does not clip quantities or split duplicate rows to circumvent limits.

`pick-a-brick.csv` contains only the two official columns and is emitted only for a fully purchasable quote. If any required elements cannot be ordered, the file is named `pick-a-brick-available.csv` and omits those elements; `missing-pieces.csv` records them. If no pieces are uploadable, no upload CSV is emitted. The complete BOM is always retained in `price-breakdown.csv` and `price.json`.

A successfully imported CSV does not guarantee future stock or checkout pricing. Reprice when ordering; upload to the same country store used for the quote. If LEGO changes the uploader, inspect that store's current template before changing headers. Do not guess IDs or edit a CSV to disguise a missing part.
