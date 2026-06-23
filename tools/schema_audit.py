"""RefPMS 스키마 전체 정합성 교차검증.

소스(서로 일치해야 함):
  1. class_template_wizard.COMPONENT_GROUPS  -> 그룹별 헤더 필드 (UI 진실)
  2. data/field_values.json                  -> 그룹별 드롭다운 값 (short/long, std/category)
  3. data/item_code_db.json                  -> Item_Code 코드/code_name
  4. data_defaults.DEFAULT_COMPONENT_MAPPING -> 필수/조건부/일관성 규칙
  5. domain_schema.*_FIELDS (있으면)         -> 문서 카탈로그

검사:
  A. 헤더 필드인데 값 소스 없음 (드롭다운/외부소스 어디에도 없음)
  B. field_values 에 있는데 헤더에 없음 (죽은 값 목록)
  C. mapping 규칙이 가리키는 필드가 헤더에 없음 (orphan 규칙)
  D. 필수 필드인데 채울 옵션이 없음 (저장 불가)
  E. Matl_Code 의 std/category 가 Matl_Std/Matl_Category 에 없음 (참조 깨짐)
  F. item_code_db: 그룹 누락 / code_name 누락
  G. domain_schema 필드명 vs 헤더 (문서 드리프트) — 있으면
"""
import json, sys
sys.path.insert(0, "src")

from class_template_wizard import COMPONENT_GROUPS

FV = json.load(open("data/field_values.json", encoding="utf-8"))
ICDB = json.load(open("data/item_code_db.json", encoding="utf-8"))
from data_defaults import DEFAULT_COMPONENT_MAPPING as MAP

# 외부 소스로 값이 오는 필드 (field_values 에 없어도 정상)
EXTERNAL = {
    "Class_Name", "Item_Code",
    "Size_From", "Size_To", "Size1_From", "Size1_To", "Size2_From", "Size2_To",
    "Remarks", "Bolt_Length_Table",
}

headers_by_group = {sn: [h for h in headers] for sn, _l, headers in COMPONENT_GROUPS}
sheets_map = MAP.get("sheets", {})

issues = {k: [] for k in "ABCDEFGH"}

def fv_fields(group):
    return set((FV.get(group) or {}).keys())

def fv_options(group, field):
    return [it for it in (FV.get(group) or {}).get(field, [])]

# ---- A & B: 헤더 <-> field_values 정합 ----
for group, headers in headers_by_group.items():
    hset = set(headers)
    fvset = fv_fields(group)
    for f in headers:
        if f in EXTERNAL:
            continue
        if f not in fvset:
            issues["A"].append(f"{group}: 헤더 '{f}' 값 소스 없음 (field_values 미존재)")
    for f in fvset:
        if f not in hset:
            issues["B"].append(f"{group}: field_values '{f}' 가 헤더에 없음 (죽은 값 목록)")

# ---- F: item_code_db ----
for group in headers_by_group:
    items = ICDB.get(group)
    if not items:
        issues["F"].append(f"{group}: item_code_db 그룹 누락")
        continue
    for it in items:
        if not (it.get("code_name") or "").strip():
            issues["F"].append(f"{group}: code={it.get('code')!r} code_name 비어있음")

# ---- C & D: mapping 규칙 정합 ----
for group, rules in sheets_map.items():
    hset = set(headers_by_group.get(group, []))
    if not hset:
        issues["C"].append(f"{group}: mapping 에 있으나 COMPONENT_GROUPS 에 그룹 없음")
        continue
    req = rules.get("required_non_empty", [])
    for f in req:
        if f not in hset:
            issues["C"].append(f"{group}: required '{f}' 헤더에 없음")
        else:
            # D: 채울 수단 있나
            if f not in EXTERNAL and not fv_options(group, f):
                issues["D"].append(f"{group}: required '{f}' 채울 옵션 없음 (저장 불가 위험)")
    for cond in rules.get("conditional_required", []):
        for key in ("when_field",):
            wf = cond.get(key)
            if wf and wf not in hset:
                issues["C"].append(f"{group}: conditional_required.when_field '{wf}' 헤더에 없음")
        for f in cond.get("require_non_empty", []):
            if f not in hset:
                issues["C"].append(f"{group}: conditional_required.require_non_empty '{f}' 헤더에 없음")
    for cond in rules.get("conditional_empty", []):
        wf = cond.get("when_field")
        if wf and wf not in hset:
            issues["C"].append(f"{group}: conditional_empty.when_field '{wf}' 헤더에 없음")
        for f in cond.get("require_empty", []):
            if f not in hset:
                issues["C"].append(f"{group}: conditional_empty.require_empty '{f}' 헤더에 없음")
    for cc in rules.get("code_category_consistency", []):
        for key in ("code_field", "category_field"):
            f = cc.get(key)
            if f and f not in hset:
                issues["C"].append(f"{group}: code_category_consistency.{key} '{f}' 헤더에 없음")

# 그룹이 mapping 에 아예 없는 경우
for group in headers_by_group:
    if group not in sheets_map:
        issues["C"].append(f"{group}: DEFAULT_COMPONENT_MAPPING 에 그룹 규칙 없음")

# ---- E: Matl_Code std/category 참조 ----
CODE_FIELDS = {  # code_field -> (std_field, category_field)
    "Matl_Code": ("Matl_Std", "Matl_Category"),
    "Bolt_Matl_Code": ("Bolt_Matl_Std", "Bolt_Matl_Category"),
    "Nut_Matl_Code": ("Nut_Matl_Std", None),
}
for group in headers_by_group:
    g = FV.get(group) or {}
    for code_field, (std_field, cat_field) in CODE_FIELDS.items():
        codes = g.get(code_field)
        if not codes:
            continue
        std_shorts = {it.get("short") for it in g.get(std_field, [])} if std_field else None
        cat_shorts = {it.get("short") for it in g.get(cat_field, [])} if cat_field else None
        for it in codes:
            s = it.get("std")
            if std_shorts is not None and s is not None and s not in std_shorts:
                issues["E"].append(f"{group}.{code_field}: code={it.get('short')!r} std={s!r} 가 {std_field} 에 없음")
            c = it.get("category")
            if cat_shorts is not None and c is not None and c not in cat_shorts:
                issues["E"].append(f"{group}.{code_field}: code={it.get('short')!r} category={c!r} 가 {cat_field} 에 없음")

# ---- G: domain_schema 문서 드리프트 (상수명 = <GROUP>_FIELDS) ----
try:
    import domain_schema as DS
    for group, headers in headers_by_group.items():
        const = group.upper() + "_FIELDS"
        fields = getattr(DS, const, None)
        if fields is None:
            issues["G"].append(f"{group}: domain_schema.{const} 없음")
            continue
        ds_names = [getattr(fd, "name", None) for fd in fields]
        hset = set(headers)
        ds_set = set(ds_names)
        for n in ds_names:
            if n not in hset:
                issues["G"].append(f"{group}: domain_schema 필드 '{n}' 헤더에 없음")
        for h in headers:
            if h not in ds_set:
                issues["G"].append(f"{group}: 헤더 '{h}' domain_schema 에 없음")
except Exception as e:
    issues["G"].append(f"domain_schema 로드 실패: {e}")

# ---- H: 서술 필드 short 가 약어가 아니라 풀단어 (예: Bolted -> BB 여야 함) ----
# 재료/규격 필드는 designation 자체가 표준이라 제외. 서술(categorical) 필드만 검사.
DESCRIPTOR_FIELDS = {
    "Bonnet_Type", "Bonnet_Stem", "Operation", "Wedge_Type", "Disc_Type",
    "Body_Type", "Bore", "Entry_Type", "End_Type", "Facing",
    "Manufacturing_Method", "Gasket_Type", "Flange_Type",
    "Bolt_Type", "Nut_Type", "Plug_Type",
}
for group in headers_by_group:
    g = FV.get(group) or {}
    for field in g:
        if field not in DESCRIPTOR_FIELDS:
            continue
        for it in g[field]:
            short = (it.get("short") or "").strip()
            long = (it.get("long") or "").strip()
            if not short:
                continue  # (None) 옵션
            # 약어 코드라면 소문자가 없어야 한다 (BW/RF/OS&Y/PSB...). 소문자 포함 = 풀단어.
            if any(c.islower() for c in short):
                issues["H"].append(f"{group}.{field}: short={short!r} (long={long!r}) — 약어 아님")

# ---- 리포트 ----
TITLES = {
    "A": "A. 헤더 필드인데 값 소스 없음",
    "B": "B. field_values 에 있는데 헤더에 없음 (죽은 값)",
    "C": "C. mapping 규칙이 가리키는 필드가 헤더에 없음",
    "D": "D. 필수인데 채울 옵션 없음 (저장 불가 위험)",
    "E": "E. Matl_Code std/category 참조 깨짐",
    "F": "F. item_code_db 누락",
    "G": "G. domain_schema 문서 드리프트",
    "H": "H. 서술 필드 short 가 약어 아님 (풀단어)",
}
total = 0
for k in "ABCDEFGH":
    lst = issues[k]
    total += len(lst)
    print(f"\n### {TITLES[k]}  ({len(lst)})")
    if not lst:
        print("   OK")
    for line in lst:
        print("   -", line)
print(f"\n==== 총 이슈: {total} ====")
