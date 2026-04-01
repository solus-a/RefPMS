# RefPMS: Universal Data Engine Completion Plan

This document outlines the strategic roadmap to evolve RefPMS from a "file converter" into a "Universal Data Engine" based on the **5-Layer Hierarchical Schema** defined in `PROJECT_HISTORY.md`.

---

## Phase 0: Schema & Architectural Decisions
**Goal:** Finalize the "Global Schema" and "Data Structure" before implementation.

### Key Questions for the User:
1. **Unit System Strategy**: 단일 프로젝트 내에서 Inch와 Metric을 혼용해야 합니까, 아니면 프로젝트 설정(Layer 1)에서 하나만 선택하도록 강제합니까?
2. **Mandatory Atomic Attributes**: 모든 부품군(Pipe, Fitting, Valve 등)이 공통적으로 가져야 하는 "최소 원자 속성"은 무엇입니까? (예: Material, Grade, Manufacturing Method, Standard)
3. **Item Code Logic**: Item Code(Commodity Code) 생성 규칙은 고정입니까, 아니면 프로젝트별로 템플릿화하여 변경 가능해야 합니까?
4. **Data Normalization**: 최종 출력물에서 모든 데이터를 하나의 시트에 통합할까요, 아니면 현재처럼 부품군별로 시트를 분리하여 유지할까요?
5. **Vendor Data Handling**: 표준 규격품(Standard)과 벤더 특정 제품(Vendor-specific)을 스키마 레벨에서 어떻게 구분하여 관리하길 원하십니까?

---

## Phase 1: Layer 1 - Project Context Externalization
**Goal:** Remove hardcoded constants and allow project-specific "Laws of Physics."

### Key Tasks:
1. **Create `project_config.json`**: Move `NPS_LIST`, units (Inch/Metric), and global coding rules from `pms_generator.py` to this file.
2. **Update `config.py`**: Add a loader for `project_config.json` so other modules can access project-wide settings.
3. **Refactor `pms_generator.py`**: Replace internal constants with calls to the new configuration manager.

---

## Phase 2: Layer 2 - Class/Spec Technical Envelope
**Goal:** Formalize the engineering constraints and thickness/rating lookup tables.

### Key Tasks:
1. **Class Specification Model**: Create a Python class (e.g., `ClassSpec`) to hold Layer 2 data: Design Code (ASME B31.3), P/T Rating, Corrosion Allowance, and Service Fluid.
2. **Enhanced Thickness Engine**: Refactor `_lookup_schedule_thickness` into a robust `ThicknessEngine` that handles complex mappings (e.g., size-specific schedules) and interpolation rules.
3. **Technical Envelope Validation**: Implement checks to ensure that any component (Layer 4) assigned to a class respects its rating and material constraints.

---

## Phase 3: Layer 3 - Group Logic Generalization
**Goal:** Make the engine "category-agnostic" so adding new components doesn't require code changes.

### Key Tasks:
1. **Mapping Configuration**: Create a `component_mapping.json` that defines which attributes are required for each `Item_Code` group (Pipe, Fitting, Valve, etc.).
2. **Dynamic Validator**: Implement a check that ensures every "Atomic" record (Layer 5) has all the attributes required by its "Group" (Layer 3).

---

## Phase 4: Layer 4 - Attribute Atomization (Engineering DNA)
**Goal:** Stop treating descriptions as simple strings and start treating them as structured data.

### Key Tasks:
1. **Define Attribute Schema**: Create a structured format to store individual attributes (Material, Grade, Method, End Types, Geometry) as discrete data points.
2. **Refactor Description Rules**: Change `_build_item_description_by_rule` to return an **Attribute Map** instead of a concatenated string.
3. **Delayed String Generation**: Create a `formatter.py` that generates final descriptions from the Attribute Map based on customizable templates.

---

## Phase 5: Layer 5 - Atomic Generation & Export
**Goal:** Finalize the discrete data points and provide flexible output.

### Key Tasks:
1. **Atomic Record Finalization**: Ensure Layer 5 records inherit and calculate all properties from Layers 1-4 (e.g., final calculated weight or length).
2. **Multi-Format Export**: Support exporting the "Atomic Layer" data into Excel, JSON, or SQL formats.
3. **GUI & Progress**: Add a progress bar and a "Validation Report" view to show engineering errors found during generation.

---

## Success Criteria
- [ ] No hardcoded engineering constants in `.py` files.
- [ ] Final output contains both the "Structured Attributes" (Columns) and the "Final Description" (String).
- [ ] New component groups can be added by editing configuration files only.
- [ ] 100% validation coverage for NPS vs. Schedule mapping and Class-level constraints.
