# CODING_STYLE.md — Non-Negotiable

## 1. Immutability (CRITICAL)
Return new objects. Do not mutate inputs. This applies to settings, config snapshots, class-level bundles, size-range structures, and any value passed across module boundaries. Mutation hides causes and breaks reasoning.

## 2. KISS / DRY / YAGNI
- **KISS** — the simplest thing that actually works. Clarity over cleverness.
- **DRY** — extract when repetition is real, not speculative. Three near-duplicates beat a premature abstraction.
- **YAGNI** — do not build for hypothetical futures. No feature flags, fallbacks, or shims for scenarios that cannot occur.

## 3. Validate at Boundaries, Trust the Interior
Validate user input, file contents, and external data at the edge. Inside the engine, trust your callers. Defensive code at every layer is noise, not safety.

## 4. Error Handling
Handle errors explicitly; never swallow them silently. Logic raises; UI decides presentation. Error messages must be actionable — name the constraint that failed and the value that failed it.

## 5. File Size and Cohesion
Prefer many small, focused files over few large ones.

**Engine / service modules** (`pms_generator`, `class_spec`, `validator`, `project_constraints`, etc.):
200–400 lines is typical, 800 is the hard ceiling. Growing past that is a signal that responsibilities have mixed — extract utilities by responsibility, not by type.

**UI wizard / dialog files** (`class_template_wizard`, `project_settings_dialog`, etc.):
No hard line. tkinter has no component model, so a multi-tab wizard accumulates setup, event handlers, and refresh logic that cannot be split across files without artificial seams. Keep cohesion by grouping private helpers near the method that uses them, and extract self-contained helper classes (dialogs, validators, formatters) into the same file or a dedicated `_helpers` module when they grow large enough to obscure the main class.

**SSOT definition files** (`domain_schema.py`):
No hard line. A file with zero functions that exists only to declare metadata (`FieldDefinition` lists per sheet) has a single responsibility by construction — splitting it scatters the SSOT, breaks cross-sheet comparison (e.g. Gate vs Globe disc options), and forces the non-developer domain expert to navigate multiple files to read related domain context. Keep cohesion through per-sheet header comments (`# ── <Sheet>_Group ──`) that demarcate sections and carry the domain rationale.

## 6. Naming
- Python code is `snake_case` by default.
- Existing rule-style helpers use `camelCase` (e.g. schedule-rule normalizers). Match the surrounding file's convention; do not mass-rename.
- Booleans read as predicates: `is_…`, `has_…`, `should_…`, `can_…`.
- Constants are `UPPER_SNAKE_CASE`. Classes are `PascalCase`.

## 7. Code Smells to Avoid
- Deep nesting — use early returns.
- Magic numbers — name meaningful thresholds.
- Long functions — split by responsibility.
- Comments that restate the code — a good name replaces a comment. Comments are reserved for non-obvious *why*.

## 8. Data File Conventions
The `long` field in `data/field_values.json` carries only the natural-language expansion of `short` — one line, no parenthetical asides. Put standard names, applicable conditions, domain conventions, and design rationale in `src/domain_schema.py` (the `FieldDefinition.meaning` field or the sheet header comment), never in the option pool.

| short | long (correct) | long (anti-pattern) |
|---|---|---|
| `Swing` | `Swing Disc` | `Swing Disc (hinge 회전, 2"+ 대구경 표준; API 6D)` |
| `150#` | `Class 150` | `Class 150 (ASME B16.34)` |
| `""` | `(unspecified)` | `(unspecified — Procurement Description 미기재 케이스 허용)` |

The `data/field_values.json` pool is consumed by the wizard combo box at runtime; users see `long` as the readable label. Anything beyond the natural-language expansion belongs in the schema module, where engineers read it.

Two narrow exceptions to "natural-language only":

1. **Domain abbreviations that are already the natural-language form.** Industry-standard tokens like `ASTM`, `13Cr`, `PTFE`, `SS304` have no readable expansion that adds clarity — engineers read the abbreviation as the term. `long` may equal `short` in that case.
2. **Parenthetical disambiguators for thread/standard variants.** When two rows share the same natural-language meaning but differ by an established formal qualifier (e.g. `PT` vs `NPT`, both threaded ends; JIS vs ANSI variants), the long may carry the qualifier in parentheses: `"Threaded (PT)"` / `"Threaded (NPT)"`. This is the qualifier itself, not a domain note about it.
