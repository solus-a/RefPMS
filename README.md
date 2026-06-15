# RefPMS

A transformation engine that takes project-level piping constraints, class-level definitions, and component-level item data, and generates a **Micro DB** (`Piping_Material_Class_Data.xlsx`) for 3D plant-design systems.

- **Project principles / constitution** → `CLAUDE.md`
- **Implementation map (modules, config layout, output contract)** → `ARCHITECTURE.md`
- **Domain glossary** → `docs/domain-glossary.md`

## Common Commands

- Run the GUI: `python run.py`

## Gotchas

- `config/project/*.bak` files are created on each save (configurable) and are `.gitignore`'d.
- Generated directories `output/`, `template/`, and `build-output/` are `.gitignore`'d — don't commit sample outputs.
- Daily platform is Windows + PowerShell. In Python code, use `pathlib.Path` and forward slashes; avoid `/dev/null`.
