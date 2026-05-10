# CLAUDE.md — Project Constitution

If something below ever contradicts the code, the principles win and the code is wrong.

## 1. Mission

RefPMS is a Piping Material Classification management system. It manages piping specifications based on a Piping Component DB, Commodity Codes, and business logic.

## 2. Decision Hierarchy

Piping specifications are organized as a strict three-layer hierarchy.
Upstream layers constrain downstream layers; they never merely suggest.

Project → Class → Component

## 3. Config Boundary

Project config, Generator config, and Program-internal data are strictly separated. Never mix them. See ARCHITECTURE.md for details.

## 4. Domain Terminology

Constraint > Rule > Default

- Do not treat `Default` as mandatory — Defaults are overridable; Constraints are not.
- Do not call the lowest hierarchy level `Material` — use `Component`.

For coding conventions, see CODING_STYLE.md.
For full glossary, see docs/domain-glossary.md.
For module structure, commands, and file paths, see ARCHITECTURE.md and README.md.
For the agent-based work flow on coding requests, see WORKFLOW.md.
