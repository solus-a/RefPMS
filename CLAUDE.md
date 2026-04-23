# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RefPMS is a transformation engine that takes project-level piping constraints, class-level definitions, and component-level item data, and generates a **Micro DB** for 3D plant-design systems as `Piping_Material_Class_Data.xlsx`.

- Stack: Python, **tkinter** (GUI), **openpyxl** (Excel I/O), **PyInstaller** (packaging).
- Entry point: `run.py` launches the Tk GUI. No CLI "generate" command — generation is triggered from the UI after loading an input template.

## Common Commands

- Run the GUI: `python run.py`
- Run the result-validation harness (all cases): `python run.py harness --all`
- Run a single harness case: `python run.py harness --case <case_name>`
- Run with ad-hoc paths: `python run.py harness --input <template.xlsx> --expected <expected.xlsx>`
- Run the unittest wrapper around the harness: `python -m unittest tests.test_harness -v`

Harness cases live under `tests/input/<case_name>/Class_Define_Template.xlsx` and must mirror `tests/expected/<case_name>/Piping_Material_Class_Data.xlsx`. When output behavior changes intentionally, add/update a harness case rather than documenting the diff in prose.

## Architecture — the Decision Hierarchy

The whole system is a top-down hierarchy; upstream **Constraints** narrow downstream choices. Internalize this before editing generation or validation code:

```
Project  ──▶  Class  ──▶  Component
 (global)    (grade)    (specific item)
```

| Layer | Scope | Where it lives |
|---|---|---|
| `Project` | Global premises: design code, unit system, nominal-size system selection (**NPS or DN**), thread standards. | `config/project/*.json`, `project_constraints.py` |
| `Class` | Inherits Project + adds classification constraints + declares the **Size Range** (Size_From/Size_To columns on Class_Define). The intersection with the template-wide `Size_Selection` sheet defines the Class's active size set. | `class_spec.py`, `class_level_model.py`, `Class_Define` + `Size_Selection` sheets |
| `Component` | Inherits Class + shape/spec to uniquely identify an item. | Component sheets, `data/component_mapping.json`, `data/Item_Code_DB.xlsx` |

The **size catalog itself** (ASME B36.10 NPS / ISO 6708 DN, with a `preferred` flag) is a program-internal, immutable dataset at `data/nps_catalog.json`. Project selects *which* system; Class declares *which subset* is active. Do not treat `nps_catalog.json` as user config.

## Config Boundary (critical)

- `config/project/*` = project-level **Constraints** (SSOT). Only domain constraints — no behavior.
- `config/generator/*` = generation/validation **execution policy** (`output_settings.json`, `coding_rules.json`, `validation_policy.json`).
- `data/*` = program-internal datasets (size catalog, mappings, Item_Code_DB).

Do NOT put generator behavior, validation policy, UI defaults, or runtime toggles under `config/project/`. The boundary is enforced in code (`config.py`) and in the terminology rules.

All config is loaded through the `ProjectConfig` singleton in `src/config.py`; read values via `config.config_manager.get("dotted.key")`. On load/reload, `validate_project_constraints` runs and surfaces warnings.

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

Keep business logic in the engine modules (`pms_generator`, `class_spec`, `thickness_engine`, `validator`, `project_constraints`). `gui.py` / `main.py` / `controller.py` must not implement domain rules.

## UI ↔ Logic Separation

- tkinter imports are allowed **only** in UI-layer files. Engine/service modules must be pure Python.
- Logic raises exceptions for domain/validation errors; the UI layer catches them and decides how to present them (status bar, messagebox, …). Never call `messagebox` from business-logic modules.
- Inject UI actions (file pickers, dialogs) via callbacks — see how `controller.py` wires `gui.build_gui` and `project_config_service.save_and_reload`.

## Coding Style (non-obvious rules)

- **Immutability is mandatory.** Return new objects; do not mutate inputs. This applies to settings/config values, class-level bundles, size-range structures, etc. See `ProjectSettings` (slotted value object) and `ProjectConfig.snapshot()` (deep-copy).
- File size guideline: 200–400 lines typical, 800 max — extract utilities when a module grows (see `excel_sheet_utils.py`, `size_matrix_common.py`).
- Validate at system boundaries (user input, file content, JSON). Trust internal callers.
- Existing code uses a mix of `snake_case` (Python norm) and `camelCase` (rule-style helpers like `normalizeScheduleValue`, `scheduleAllowlist`). Match the surrounding file's convention; don't mass-rename.

## Domain Terminology (share this vocabulary with the user)

Full glossary: `docs/domain-glossary.md`. The distinctions below are **enforced in conversation and code**:

| Term | Definition | Question |
|---|---|---|
| `Constraint` | Mandatory limit or permissible range | *What must be?* |
| `Condition` | Observable state / input fact evaluated by a Rule | *What is?* |
| `Rule` | Decision logic that combines Conditions + Constraints → outcome | *What should be decided?* |
| `Validation` | Conformance check against established criteria | *Is it valid?* |
| `Default` | Overridable standard applied when user didn't specify | *What applies if unspecified?* |

- Precedence: `Constraint > Rule > Default`. An Override at a lower scope must still satisfy all applicable Constraints.
- Name disambiguation: `RefPMS` = the software; `Project` = the domain hierarchy layer. Clarify when ambiguous.
- The lowest hierarchy level is **`Component`**, never `Material` (which collides with 재질, a mere attribute).
- Don't conflate `Rule` with `Validation` (decide vs check) or `Default` with `Constraint` (overridable vs mandatory).

## Output Contract

- Output filename: `Piping_Material_Class_Data.xlsx` (sheet `Piping_Material_Class_Data`).
- `Item_Code` ordering comes **only** from `config/generator/output_settings.json` → `item_order`.
- `pms_generator.py` is the single place that assembles the output workbook.

## Gotchas

- `config/project/*.bak` files are created on each save (configurable) and are `.gitignore`'d.
- Generated directories `output/`, `template/`, and `build-output/` are `.gitignore`'d — don't commit sample outputs into the repo; add harness cases instead.
- Harness case directory names must be **identical** between `tests/input/` and `tests/expected/`.
- Platform is Windows + PowerShell for daily work; use forward slashes in Python paths and `/dev/null` sparingly — prefer `Path` from `pathlib`.
