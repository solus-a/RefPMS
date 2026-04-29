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
Prefer many small, focused files over few large ones. 200–400 lines is typical, 800 is the ceiling. When a module grows past that, extract utilities by responsibility, not by type.

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
