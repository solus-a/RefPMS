# RefPMS

A transformation engine that takes project-level piping constraints, class-level definitions, and component-level item data, and generates a **Micro DB** (`Piping_Material_Class_Data.xlsx`) for 3D plant-design systems.

- **Project principles / constitution** → `CLAUDE.md`
- **Implementation map (modules, config layout, output contract)** → `ARCHITECTURE.md`
- **Domain glossary** → `docs/domain-glossary.md`

## Common Commands

- Run the GUI: `python run.py`
- Run the result-validation harness (all cases): `python run.py harness --all`
- Run a single harness case: `python run.py harness --case <case_name>`
- Run with ad-hoc paths: `python run.py harness --input <template.xlsx> --expected <expected.xlsx>`
- Run the unittest wrapper: `python -m unittest tests.test_harness -v`

Harness cases live under `tests/input/<case_name>/Class_Define_Template.xlsx` and must mirror `tests/expected/<case_name>/Piping_Material_Class_Data.xlsx`. Directory names must be identical on both sides. When output behavior changes intentionally, add or update a harness case rather than describing the diff in prose.

## Gotchas

- `config/project/*.bak` files are created on each save (configurable) and are `.gitignore`'d.
- Generated directories `output/`, `template/`, and `build-output/` are `.gitignore`'d — don't commit sample outputs; add harness cases instead.
- Daily platform is Windows + PowerShell. In Python code, use `pathlib.Path` and forward slashes; avoid `/dev/null`.
