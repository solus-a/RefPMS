# RefPMS Domain Glossary

This document is the **single source of truth (SSOT)** for terminology used across the RefPMS project.
Its purpose is to ensure that the **user** and **AI** share a common language when discussing domain concepts, programming concepts, and the rules that connect them.

> **Convention**: Standard terms are written in English. Each term includes a Korean explanation and, where relevant, a development-concept mapping.

---

## 0. Name Disambiguation

| Term | Meaning | Scope |
|---|---|---|
| `RefPMS` (or `프로젝트` when referring to this software) | The software itself — the transformation engine and its codebase | Development context |
| `Project` (hierarchy term) | A domain-level piping/plant construction project whose global constraints govern all Classes and Components beneath it | Domain context |

When communicating between user and AI:
- Use **RefPMS** when talking about the software, its code, its features, or its bugs.
- Use **Project** only when talking about the domain hierarchy layer (global constraints, design code, unit system, etc.).
- If ambiguity arises, always clarify: *"Do you mean RefPMS (the software) or Project (the domain hierarchy)?"*

---

## 1. Decision Hierarchy

RefPMS operates as a **top-down, hierarchical decision system**.
Upstream constraints limit the choices available downstream; domain knowledge acts at every boundary.

```
Project  ──▶  Class  ──▶  Component
 (global)    (grade)    (specific item)
```

### 1.1 Project

| Aspect | Description |
|---|---|
| English | Project |
| Korean | 프로젝트 |
| Definition | The top-level scope that establishes **global premises and constraints** shared by every class and component beneath it. |
| Examples | Design code (ASME B31.3), unit system (Metric/Imperial), nominal size notation (NPS/DN), NPS/DN master list, pipe thread standard (NPT/PT), bolt thread standard, design unit labels (°C, kPa, etc.) |
| In code | `config/project/*`, `project_constraints.py` |

### 1.2 Class

| Aspect | Description |
|---|---|
| English | Class |
| Korean | 클래스 (배관재 등급) |
| Definition | A grouping layer that inherits **Project constraints** and adds further constraints to classify piping materials into a distinct grade (Piping Material Classification). |
| Examples | Class_Base_Material (material group, e.g., KCS, SS304), Class_Rating (pressure-temperature rating, e.g., 150, 300), Corrosion_Allowance, Design_Temperature range, Design_Pressure range, Fluid_Service |
| In code | `class_spec.py`, `Class_Define` sheet in the template |

### 1.3 Component

| Aspect | Description |
|---|---|
| English | Component |
| Korean | 컴포넌트 (개별 자재 항목) |
| Definition | The lowest level of the hierarchy. Within a Class, a Component is a **single, fully specified item** whose shape, characteristics, and detailed specifications have been determined to make it unique. |
| Examples | A specific elbow (type, size, schedule, rating, material), a specific gasket (type, size, class, material) |
| In code | Rows in template component sheets, `component_mapping.json`, `Item_Code_DB.xlsx` |

> **Prohibited synonym**: Do NOT use `Material` as the name of this hierarchy level. `Material` in Korean can be confused with `재질` (metallurgical material), which is only one attribute of a Component.

---

## 2. Core Concept Terms

### 2.1 Constraint

| Aspect | Description |
|---|---|
| English | Constraint |
| Korean | 제약 — 반드시 지켜야 하는 제한 또는 허용 범위 |
| Definition | A **mandatory limit or permissible range** that must be respected. Constraints are not optional; violating them is always an error. |
| Relationship | Upstream constraints narrow downstream choices. `Project constraints` limit `Class`; `Class constraints` limit `Component`. |
| Examples | "Design pressure must not exceed the flange rating", "Only NPS values defined in nps_master are allowed" |
| In code | `config/project/*` values, validation checks in `project_constraints.py` |

### 2.2 Condition

| Aspect | Description |
|---|---|
| English | Condition |
| Korean | 조건 — 결정을 내리기 위해 평가하는 상태, 전제, 입력 사실 |
| Definition | An **observable state, premise, or input fact** evaluated when making a decision. Conditions do not enforce limits by themselves; they serve as inputs to Rules. |
| Examples | "The fluid is corrosive", "Temperature range is -29 to 427 °C", "The class uses socket-weld connections" |
| Contrast with Constraint | A Condition describes *what is*; a Constraint describes *what must be*. |

### 2.3 Rule

| Aspect | Description |
|---|---|
| English | Rule |
| Korean | 규칙 — 조건(Condition)과 제약(Constraint)을 바탕으로 결과를 결정하는 판단 로직 |
| Definition | A **decision logic** that takes Conditions and Constraints as inputs and **determines** an outcome. Rules are designed from Domain Knowledge. |
| Examples | "If fluid is corrosive AND temperature ≤ 200 °C, select SS316L material group", "If NPS ≥ 2″, default to butt-weld connection" |
| Contrast with Validation | A Rule answers *"what should be decided?"*; Validation answers *"is the input valid?"* |
| In code | Logic in `pms_generator.py`, `class_spec.py`, mapping JSONs |

### 2.4 Validation

| Aspect | Description |
|---|---|
| English | Validation |
| Korean | 검증 — 입력값, 설정값, 연결 관계가 정해진 기준에 맞는지 확인하는 검사 |
| Definition | A **conformance check** that verifies whether an input, setting, or relationship meets the established criteria. Validation does not decide outcomes; it confirms or rejects. |
| Examples | "Required field is missing", "Size-schedule combination does not exist in the thickness table", "Branch table references an undefined class" |
| In code | `validator.py`, `project_constraints.py` (pre-generation checks) |

### 2.5 Default

| Aspect | Description |
|---|---|
| English | Default |
| Korean | 기본 선택값 — 별도 지정이 없을 때 우선 적용되는 표준 선택 |
| Definition | The **standard selection** applied when the user has not explicitly specified a value. A Default is a convenience, not a mandate; it can always be overridden by an explicit choice. |
| Precedence | Constraints always override Defaults. If a Default conflicts with a Constraint, the Constraint wins. |
| Examples | "Default end connection is butt-weld for NPS ≥ 2″", "Default gasket type is spiral wound" |
| In code | `data_defaults.py`, default columns in template sheets |

### 2.6 Domain Knowledge

| Aspect | Description |
|---|---|
| English | Domain Knowledge |
| Korean | 도메인 지식 — 예외와 우선순위를 결정하는 배경 지식이자 Rule 설계의 출처 |
| Definition | The **professional expertise** that determines exceptions, priorities, and special judgment criteria. Domain Knowledge lives outside the code but must be reflected inside Rules and Constraints. It is the **source from which Rules are designed**. |
| Examples | "ASME B16.5 class 150 flanges are not suitable above 260 °C for carbon steel", "Socket-weld is preferred over threaded for high-vibration services" |

---

## 3. Supporting Concept Terms

### 3.1 Decision

| Aspect | Description |
|---|---|
| English | Decision |
| Korean | 결정 — 조건을 종합해 최종 상태를 정하는 행위 |
| Definition | The act of synthesizing multiple Conditions and Constraints to **determine a final state**. A Decision is the output of a Rule. |

### 3.2 Mapping

| Aspect | Description |
|---|---|
| English | Mapping |
| Korean | 매핑 — 하나의 입력값 또는 조건 조합을 특정 출력값에 대응시키는 관계 |
| Definition | A **correspondence** between an input (or combination of inputs) and a specific output. Mappings are a common way to encode Rules as data. |
| In code | `component_mapping.json`, `class_material_mapping.json`, `coding_rules.json` |

### 3.3 Exception

| Aspect | Description |
|---|---|
| English | Exception |
| Korean | 예외 — 일반 Rule의 적용을 벗어나는 특수한 경우 |
| Definition | A **special case** where the general Rule does not apply and an alternative Decision is required. Exceptions are typically justified by Domain Knowledge. |

### 3.4 Priority

| Aspect | Description |
|---|---|
| English | Priority |
| Korean | 우선순위 — 여러 Rule이나 Default가 충돌할 때 어느 것을 먼저 적용할지의 순서 |
| Definition | The **order of precedence** when multiple Rules or Defaults conflict. Higher-priority items override lower-priority ones. |
| Precedence chain | Constraint > Rule > Default |

### 3.5 Scope

| Aspect | Description |
|---|---|
| English | Scope |
| Korean | 적용 범위 — 어떤 Constraint, Rule, 또는 Default가 영향을 미치는 계층 또는 대상의 범위 |
| Definition | The **extent** to which a Constraint, Rule, or Default applies. Scope is tied to the decision hierarchy: Project-scope, Class-scope, or Component-scope. |

### 3.6 Override

| Aspect | Description |
|---|---|
| English | Override |
| Korean | 재지정 — 상위 계층 또는 Default에 의해 결정된 값을 하위 계층에서 명시적으로 다른 값으로 바꾸는 행위 |
| Definition | The act of **explicitly replacing** a value determined by a higher scope or by a Default with a different value at a lower scope. An Override must still satisfy all applicable Constraints. |

### 3.7 State

| Aspect | Description |
|---|---|
| English | State |
| Korean | 상태 — 특정 시점에서 어떤 대상이 가지고 있는 값 또는 속성의 집합 |
| Definition | The **set of current values or attributes** of an object at a given point in the decision flow. |

### 3.8 Input / Output

| Aspect | Description |
|---|---|
| English | Input / Output |
| Korean | 입력 / 출력 |
| Definition | **Input**: data or settings provided by the user or upstream hierarchy. **Output**: data or files produced by the system as a result of processing. |
| In code | Input = template `.xlsx`; Output = `Piping_Material_Class_Data.xlsx` |

---

## 4. Prohibited Synonyms and Dangerous Confusions

| Dangerous Expression | Problem | Use Instead |
|---|---|---|
| "조건" alone (without qualifier) | Ambiguous — could mean Condition or Constraint | Always specify: `Condition` or `Constraint` |
| "검토 기준" | Conflates Rule and Validation | Use `Rule` for decision logic, `Validation` for conformance check |
| `Material` as hierarchy level | Confused with `재질` (metallurgical material) | Use `Component` for the lowest hierarchy level |
| "기본값" as mandatory | Implies the Default cannot be changed | Use `Default` (overridable standard) vs `Constraint` (mandatory) |
| "클래스 정의" as mere data entry | Under-represents the role of Class | Class is a **classification layer with its own constraints**, not a simple input form |
| "규칙"/"룰" interchangeably with "검증" | Blurs the boundary between deciding and checking | `Rule` = what to decide; `Validation` = is it valid |

---

## 5. Decision Flow Summary

```
┌─────────────────────────────────────────────────────────────┐
│  PROJECT                                                    │
│  Set global Constraints & Conditions                        │
│  (design code, units, NPS master, thread standards, …)      │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  CLASS                                              │    │
│  │  Inherit Project Constraints                        │    │
│  │  + Add Class-specific Constraints & Conditions      │    │
│  │  → Decide material grade / classification           │    │
│  │                                                     │    │
│  │  ┌─────────────────────────────────────────────┐    │    │
│  │  │  COMPONENT                                  │    │    │
│  │  │  Inherit Class Constraints                  │    │    │
│  │  │  + Add Component-specific specs             │    │    │
│  │  │  → Decide unique item (shape, size, …)      │    │    │
│  │  │  → Apply Defaults where not specified        │    │    │
│  │  │  → Validate final state                     │    │    │
│  │  └─────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘

  Domain Knowledge acts at every boundary:
  • Designs Rules
  • Justifies Exceptions
  • Determines Priorities
```

---

## 6. Development Concept Mapping

This section maps each standard term to its representation in the codebase.

| Standard Term | Codebase Representation |
|---|---|
| Project | `config/project/*` JSON files; `project_constraints.py` |
| Class | `Class_Define` sheet in template; `class_spec.py` |
| Component | Component sheets in template; `component_mapping.json`; `Item_Code_DB.xlsx` |
| Constraint | Values in `config/project/*`; checks in `project_constraints.py`; `validation_policy.json` |
| Condition | Input cells in template sheets; evaluated states in Rule logic |
| Rule | Decision logic in `pms_generator.py`, `class_spec.py`; mapping JSONs |
| Validation | `validator.py`; pre-generation checks in `project_constraints.py` |
| Default | `data_defaults.py`; default columns in template sheets |
| Domain Knowledge | Encoded in mapping JSONs, Rule logic, and this glossary; originates from engineering expertise |
| Mapping | `component_mapping.json`, `class_material_mapping.json`, `coding_rules.json` |
| Input | Template `.xlsx` file provided by user |
| Output | `Piping_Material_Class_Data.xlsx` generated by `pms_generator.py` |

---

## 7. UI Label Guidelines

When displaying terms in the user interface, follow these conventions:

| Context | Guideline |
|---|---|
| Hierarchy names | Use Korean: `프로젝트`, `클래스`, `컴포넌트` |
| Error messages about Constraints | Prefix with `[제약 위반]` or `[Constraint]` |
| Error messages about Validation | Prefix with `[검증 오류]` or `[Validation]` |
| Default values in forms | Mark with `(기본값)` or `(Default)` to signal overridability |
| Status/progress labels | Use action-oriented Korean: `검증 중…`, `생성 중…`, `완료` |
| Tooltips for technical terms | Show English term + Korean explanation, e.g., `Constraint — 반드시 지켜야 하는 제한` |

---

*Last updated: 2026-04-16*
