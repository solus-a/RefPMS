# CLAUDE.md — Project Constitution

This file is the top-level, invariant guidance for Claude Code in this repository.
It declares **what** RefPMS is and **why** it is structured the way it is.
It deliberately avoids naming specific files, modules, or commands — those belong in `ARCHITECTURE.md` and `README.md` and will change as the code evolves.

If something below ever contradicts the code, the principles win and the code is wrong. Fix the code (or update this file if the principle itself has genuinely changed).

---

## 1. Mission

RefPMS is a transformation engine. It consumes:

- **Project-level constraints** (global premises),
- **Class-level definitions** (classification + allowed ranges),
- **Component-level item data** (specific shapes and specs),

and it produces a **Micro DB** consumable by 3D plant-design systems.

The transformation is rule-based: upstream layers constrain downstream layers, and output is fully determined by (inputs × rules × configuration). There is no hidden state.

---

## 2. Decision Hierarchy (Domain Model)

RefPMS is organized as a strict three-layer hierarchy. Upstream layers **constrain** downstream layers; they never merely suggest.

```
Project   ──▶   Class   ──▶   Component
(global)      (grade)       (specific item)
```

| Layer | Scope |
|---|---|
| `Project` | Global premises: design code, unit system, nominal size system selection (NPS or DN), thread standards. |
| `Class` | Inherits Project, adds classification constraints, and declares the active **Size Range** (a subset of the Project-chosen size system). |
| `Component` | Inherits Class and fixes shape + specification enough to uniquely identify an item. |

### Invariants

- The **size catalog itself** (ASME B36.10 NPS / ISO 6708 DN) is a program-internal, immutable reference dataset. Project selects *which system*; Class declares *which subset*. The catalog is never user configuration.
- A Component never contradicts its Class. A Class never contradicts its Project. If a conflict is detected, it is a validation failure, not a silent override.
- The lowest hierarchy level is always `Component`, never `Material`. `Material` is one attribute of a Component, not a layer.

---

## 3. Config Boundary (Critical Separation)

Configuration is split into three kinds, each with a distinct responsibility. **Do not mix them.**

| Kind | Responsibility | What it must NOT contain |
|---|---|---|
| **Project config** | Domain constraints (SSOT for the project's premises). | Generator behavior, validation policy, UI defaults, runtime toggles. |
| **Generator config** | Execution policy for generation and validation (output settings, coding rules, validation policy). | Domain constraints, user project premises. |
| **Program-internal data** | Immutable reference datasets (size catalog, mappings, code DB). | Anything user-editable or project-specific. |

Rules:

- Project config is the **Single Source of Truth** for project-level constraints. Read through a single config accessor; never bypass it.
- Validation runs on load and on reload. Surfacing warnings early is preferable to silently accepting malformed config.
- Behavior that changes with the user's project belongs in Project config. Behavior that changes with the generation pipeline belongs in Generator config. Facts about the world (catalogs, standards) belong in program-internal data.

---

## 4. UI ↔ Logic Separation

A hard architectural boundary, not a suggestion.

- **UI-layer files** may import the GUI framework. **Engine/service/logic files** must be pure Python with zero UI imports.
- Logic raises exceptions for domain and validation errors. The UI layer catches them and decides presentation (status bar, dialog, toast, log).
- Never invoke UI alerts (message boxes, pop-ups) from business-logic modules.
- UI actions required by logic (file pickers, confirmations) are injected as callbacks, not imported.

This boundary is what allows RefPMS to be tested, scripted, and repackaged without dragging GUI state through the engine.

---

## 5. Coding Style — Non-Negotiable

### 5.1 Immutability (CRITICAL)
Return new objects. Do not mutate inputs. This applies to settings, config snapshots, class-level bundles, size-range structures, and any value passed across module boundaries. Mutation hides causes and breaks reasoning.

### 5.2 KISS / DRY / YAGNI
- **KISS** — the simplest thing that actually works. Clarity over cleverness.
- **DRY** — extract when repetition is real, not speculative. Three near-duplicates beat a premature abstraction.
- **YAGNI** — do not build for hypothetical futures. No feature flags, fallbacks, or shims for scenarios that cannot occur.

### 5.3 Validate at Boundaries, Trust the Interior
Validate user input, file contents, and external data at the edge. Inside the engine, trust your callers. Defensive code at every layer is noise, not safety.

### 5.4 Error Handling
Handle errors explicitly; never swallow them silently. Logic raises; UI decides presentation. Error messages must be actionable — name the constraint that failed and the value that failed it.

### 5.5 File Size and Cohesion
Prefer many small, focused files over few large ones. 200–400 lines is typical, 800 is the ceiling. When a module grows past that, extract utilities by responsibility, not by type.

### 5.6 Naming
- Python code is `snake_case` by default.
- Existing rule-style helpers use `camelCase` (e.g. schedule-rule normalizers). Match the surrounding file's convention; do not mass-rename.
- Booleans read as predicates: `is_…`, `has_…`, `should_…`, `can_…`.
- Constants are `UPPER_SNAKE_CASE`. Classes are `PascalCase`.

### 5.7 Code Smells to Avoid
- Deep nesting — use early returns.
- Magic numbers — name meaningful thresholds.
- Long functions — split by responsibility.
- Comments that restate the code — a good name replaces a comment. Comments are reserved for non-obvious *why*.

---

## 6. Domain Terminology (Shared Vocabulary)

Full glossary: `docs/domain-glossary.md`. The following distinctions are enforced in both code and conversation.

### 6.1 Core Concepts

| Term | Definition | Key Question |
|---|---|---|
| `Constraint` | Mandatory limit or permissible range — must be respected. | *What must be?* |
| `Condition` | Observable state or input fact that a Rule evaluates. | *What is?* |
| `Rule` | Decision logic combining Conditions + Constraints into an outcome. | *What should be decided?* |
| `Validation` | Conformance check against established criteria. | *Is it valid?* |
| `Default` | Overridable standard applied when unspecified; never overrides a Constraint. | *What applies if unspecified?* |
| `Domain Knowledge` | Professional expertise behind exceptions and priorities; the source Rules are designed from. | *Why this rule?* |

### 6.2 Precedence

```
Constraint  >  Rule  >  Default
```

An override at a lower scope must still satisfy all applicable Constraints.

### 6.3 Prohibited Confusions

- Do not use bare "조건" — always specify `Condition` or `Constraint`.
- Do not conflate `Rule` with `Validation` — Rule *decides*, Validation *checks*.
- Do not treat `Default` as mandatory — Defaults are overridable; Constraints are not.
- Do not call the lowest hierarchy level `Material` — use `Component`.
- Do not reduce `Class` to a data-entry form — it is a classification layer with its own constraints.

### 6.4 Name Disambiguation

- `RefPMS` — this software.
- `Project` — the domain hierarchy layer whose global constraints govern Classes and Components.
- When ambiguous, clarify explicitly.

---

## 7. Output Contract

- RefPMS produces exactly one canonical output artifact per run — the Micro DB workbook for the downstream 3D system.
- Item ordering in the output is determined **only** by Generator config, never by input order or ad-hoc heuristics.
- Output assembly is centralized in a single engine module. There is one assembler, not many.

(Specific filenames and sheet names live in `ARCHITECTURE.md`.)

---

## 8. What Belongs Elsewhere

This file is deliberately silent about:

- **Specific module names, file paths, commands** → see `ARCHITECTURE.md` and `README.md`.
- **How to run, test, or package** → see `README.md`.
- **Recent decisions, in-progress work, debugging notes** → these live in commits, PRs, and the task tracker, not here.

If you find yourself wanting to add a file path or a command to this file, you are almost certainly writing in the wrong document.
