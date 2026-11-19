# Architecture

Implementation-level map of RefPMS. Unlike `CLAUDE.md` (principles, invariant), this file names specific modules and will be updated when the code is restructured.

## Stack

- Python
- tkinter (GUI)
- openpyxl (Excel I/O)
- PyInstaller (packaging)

## Entry Point

`run.py` launches the Tk GUI (`main.py` → `controller.py`). The main window has only **New Project** / **Open Project**; everything after that (Save Project, Export xlsx, Close) happens inside the Class Template Wizard.

PMS generation is not wired to the GUI yet. Run it on an exported template: `python src/pms_generator.py <Class_Define_Template.xlsx>`.

## Module Roles

| Module | Role |
|---|---|
| `controller.py` | Orchestration between GUI and engine — flow control only, no business rules. |
| `gui.py`, `main.py` | UI and entrypoint only. |
| `class_template_wizard.py`, `size_matrix_*` | Class Template Wizard (Global Setting / Class_Define / Reducing Tables / Branch Tables / Components tabs; Save Project / Export xlsx) and the size-matrix editor for Reducing/Branch tables (UI). |
| `file_handler.py` | File and folder dialogs (project open/save, export folder). |
| `project_codec.py` | Project file (JSON) ↔ `ClassLevelBundle` save/load. The project file is the source of truth; xlsx is only an export. |
| `class_level_model.py` | In-memory project model (`ClassLevelBundle`, `ClassTemplateGlobalSettings`, `SizeSelection`) and its row-level checks. |
| `domain_schema.py` | Domain field schema SSOT — headers, required flags, allowed values and row rules for every sheet. |
| `template_generator.py` | Export the bundle to `Class_Define_Template.xlsx` (Export xlsx), and read a template workbook back into a bundle. |
| `pms_generator.py` | Main transformation pipeline: template → `Piping_Material_Class_Data.xlsx`. |
| `class_spec.py` | `Class_Define` → class technical envelope (material, rating, temp/pressure, etc.). |
| `thickness_engine.py` | Size/class → Schedule (thickness) lookup against the `Schedule` sheet or the bundle's schedule rows. |
| `validator.py` | Per-row template validation driven by the component mapping derived from `domain_schema.py` (`data_defaults.DEFAULT_COMPONENT_MAPPING`); includes `validate_size_range_for_row`. |
| `data_defaults.py` | Overridable default values seeded into templates. |
| `excel_sheet_utils.py`, `units_notation_headers.py` | Shared helpers: worksheet header/cell reading; `Class_Define` storage vs display (unit-suffixed) headers. |

Business logic belongs in the engine modules (`pms_generator`, `class_spec`, `thickness_engine`, `validator`, `domain_schema`). UI-layer files (`gui.py`, `main.py`, `controller.py`) must not implement domain rules.

## Config Layout

- Project files (`*.json`, saved wherever the user chooses via Save Project) — the project's source of truth: global settings, `Class_Define` rows, size tables, component rows. Read and written only by `project_codec.py`.
- `config/generator/*.json` — generation/validation execution policy (`output_settings.json`, `coding_rules.json`, `validation_policy.json`).
- `data/*` — program-internal datasets: `nps_catalog.json` (size catalog), `nps_dn_pairing.json`, `nominal_size_systems.json`, `unit_systems.json`, `design_codes.json`, `class_material_mapping.json`, `field_values.json`, `item_code_db.json`. The component mapping is not a file: it is derived in memory from `domain_schema.py`.

`src/config.py` holds the path helpers (`data_dir()`, `generator_config_dir()`, …), the catalog loaders, and the `GeneratorConfig` singleton, which merges `config/generator/*` with the built-in size catalog. Read values via `config.config_manager.get("dotted.key")`. Project and class values (unit system, nominal size system, design code, …) are not stored there; they come from the project file.

The wizard validates the bundle on Save Project and Export xlsx (`ClassLevelBundle.validate()` and `validation_warnings()`).

## Domain-to-Code Mapping

| Domain Term | Where in Code |
|---|---|
| Project-level settings | Global Setting tab → `ClassTemplateGlobalSettings` in `class_level_model.py` (unit system, design temperature/pressure units, Size Selection), stored in the project file |
| Size catalog (program-internal) | `data/nps_catalog.json` |
| Class definition | `Class_Define` tab/sheet, `class_spec.py` |
| Class Size Range | `Size_From` / `Size_To` in `Class_Define` ∩ Global Size Selection → `ClassLevelBundle.active_sizes_for_class` (`class_level_model.py`); `validator.load_class_size_ranges` for template workbooks |
| Component specification | Components tab / component group sheets, field definitions in `domain_schema.py`, `field_values.json`, `item_code_db.json` |
| Rule logic | `pms_generator.py`, `class_spec.py`, row rules in `domain_schema.py`, mapping JSONs |
| Validation | `validator.py`, `ClassLevelBundle.validate()` in `class_level_model.py` |
| Defaults | `data_defaults.py`, default columns in template |

## Output Contract (Concrete)

- Output file: `Piping_Material_Class_Data.xlsx`, sheet `Piping_Material_Class_Data`.
- `Item_Code` ordering comes **only** from `config/generator/output_settings.json` → `item_order`.
- `pms_generator.py` is the single place that assembles the output workbook.
