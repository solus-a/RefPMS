# Architecture

Implementation-level map of RefPMS. Unlike `CLAUDE.md` (principles, invariant), this file names specific modules and will be updated when the code is restructured.

## Stack

- Python
- tkinter (GUI)
- openpyxl (Excel I/O)
- PyInstaller (packaging)

## Entry Point

`run.py` launches the Tk GUI. Generation is triggered from the UI after loading an input template. There is no CLI "generate" command.

## Module Roles

| Module | Role |
|---|---|
| `controller.py` | Orchestration between GUI and engine — flow control only, no business rules. |
| `gui.py`, `main.py` | UI and entrypoint only. |
| `project_settings_dialog.py`, `project_config_service.py` | Project-settings UI + load/validate/save/backup/reload of `config/project/*`. |
| `class_template_wizard.py`, `size_matrix_*` | Class-level wizard and Size Range editor (UI). |
| `template_generator.py` | Build or re-open the `Class_Define_Template.xlsx` input workbook. |
| `pms_generator.py` | Main transformation pipeline: template → `Piping_Material_Class_Data.xlsx`. |
| `class_spec.py` | `Class_Define` → class technical envelope (material, rating, temp/pressure, etc.). |
| `thickness_engine.py` | Size/class → Schedule (thickness) lookup against the `Schedule` sheet. |
| `validator.py` | Per-row template validation driven by `data/component_mapping.json`; includes `validate_size_range_for_row`. |
| `project_constraints.py` | Validates the merged project-level config before generation. |
| `data_defaults.py` | Overridable default values seeded into templates. |

Business logic belongs in the engine modules (`pms_generator`, `class_spec`, `thickness_engine`, `validator`, `project_constraints`). UI-layer files (`gui.py`, `main.py`, `controller.py`) must not implement domain rules.

## Config Layout

- `config/project/*.json` — project-level constraints (SSOT).
- `config/generator/*.json` — generation/validation execution policy (`output_settings.json`, `coding_rules.json`, `validation_policy.json`).
- `data/*` — program-internal datasets: `nps_catalog.json` (size catalog), `component_mapping.json`, `class_material_mapping.json`, `Item_Code_DB.xlsx`.

Config is loaded through the `ProjectConfig` singleton in `src/config.py`. Read values via `config.config_manager.get("dotted.key")`. On load/reload, `validate_project_constraints` runs and surfaces warnings.

## Domain-to-Code Mapping

| Domain Term | Where in Code |
|---|---|
| Project constraints | `config/project/*`, `project_constraints.py` |
| Size catalog (program-internal) | `data/nps_catalog.json` |
| Class definition | `Class_Define` sheet, `class_spec.py` |
| Class Size Range | `Class_Size_Range` sheet, `ClassSizeRange` in `class_level_model.py` |
| Component specification | Component sheets, `component_mapping.json`, `Item_Code_DB.xlsx` |
| Rule logic | `pms_generator.py`, `class_spec.py`, mapping JSONs |
| Validation | `validator.py`, `project_constraints.py` |
| Defaults | `data_defaults.py`, default columns in template |

## Output Contract (Concrete)

- Output file: `Piping_Material_Class_Data.xlsx`, sheet `Piping_Material_Class_Data`.
- `Item_Code` ordering comes **only** from `config/generator/output_settings.json` → `item_order`.
- `pms_generator.py` is the single place that assembles the output workbook.
