# Entity extraction

Extract typed entities from free-text XLSX columns using GLiNER and rule-based
event detection. This project is the extraction step for
[source-data-transformer](https://github.com/matteoLorenzini/source-data-transformer).

## Install

Requires Python 3.12 or later:

```bash
pip install .
```

For CPU-only PyTorch, install its CPU build before installing this project:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install .
```

The default model, `urchade/gliner_multi-v2.1`, is downloaded from Hugging Face
on first use and cached locally. Use `--gliner-model` to change it and
`--threshold` to adjust the confidence threshold (default `0.4`).

## Extract

```bash
python extract_entities.py --file /path/to/Person.xlsx --fields Biography Role Contribution
```

The default outputs are `output_data/Person_entities.json` and
`output_data/Person_entities_timeline.xml`. Use `--output` to select an existing
cache (including one created before the repository split), `--xml-output` to
choose the timeline path, or `--no-xml` to skip the timeline. `--sheet-name`,
`--subject-field`, and `--id-field` select the input. Run with `--help` for all
options.

The JSON caches extraction per field and text. `--dry-run` previews work without
loading the model, `--refresh` re-extracts cached cells, and `--prune` removes
cells no longer present in the workbook. `--prune` cannot be combined with
`--sheet-name`; preview it with `--dry-run --prune`. Cells extracted with a
different model are re-extracted. Rule-detected events are completed from their
source sentence and cached cells are revisited for event completion.

The timeline XML has one `<person>` per subject and date-ordered `<entry>`
elements for events, roles, works, births and deaths. Undated roles without a
place or organization are occupations. It can be mapped to CIDOC-CRM using
`mappings/e21_timeline.yaml` in source-data-transformer.

## Integration contract

Pass the JSON to source-data-transformer using `--entities`. The transformer
matches entries against its input workbook, so both commands must use the same
source text and column headers. The JSON store has `version`, `model`, and
`items` fields; each item contains its canonical `field`, subject information,
extractor, preview, and `entities`. Entity `type`, `value`, and `context` are
required; dates, places, organizations, relations, URLs and participants may
also be present.

The item key is SHA-256 of UTF-8 `6\0{field}\0{cleaned_text}`. The field is
the sanitized uppercase header; cleaning removes HTML comments, replaces
non-breaking spaces with spaces, and strips leading and trailing whitespace.
This key and the JSON entity fields are shared with the transformer and must
remain compatible when either project changes.

```bash
# In source-data-transformer/script:
python download_drive_excel.py --file /path/to/Person.xlsx \
  --stylesheet-map xslt/person.xsl --entities /path/to/Person_entities.json
python xml_to_rdf.py --mapping mappings/e21_timeline.yaml \
  --xml /path/to/Person_entities_timeline.xml --out person_timeline.ttl
```

## Tests

```bash
python -m unittest discover -s tests
```

Tests use a fake model and do not download model weights.
To also test the JSON and timeline outputs against a local transformer checkout,
install that project's dependencies and run:

```bash
TRANSFORMER_REPO=/path/to/source-data-transformer python -m unittest discover -s tests
```
