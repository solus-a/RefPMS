# 참고 규격 (docs/standards)

RefPMS 도메인 판단의 근거가 되는 국제 규격 원문 모음.

- **PDF는 저작권 문서라 git에 올리지 않는다** (`.gitignore`: `docs/standards/**/*.pdf`). 이 목록만 커밋한다.
- 파일명 규칙: `<기관>_<번호>-<판>_<제목>.pdf` — 번호(`B16.9`)나 제목 키워드(`Buttwelding`)로 찾는다.
- 텍스트 검색: `pypdf`로 추출 (`python -c "import pypdf; ..."`). **스캔본**(아래 표 "텍스트 ✗")은 텍스트가 없어 페이지 이미지를 꺼내 봐야 한다 (`pip install pillow`, `page.images`).

## 목록

| 파일 | 규격 | 판 | 텍스트 | RefPMS 관련 |
|---|---|---|---|---|
| `ASME_B31.3-2018_Process-Piping.pdf` | ASME B31.3 Process Piping | 2018 | ✓ | Class `Design_Code` (현재 유일한 설계 코드) |
| `ASME_B36.10-2022_Welded-and-Seamless-Wrought-Steel-Pipe.pdf` | ASME B36.10 Welded and Seamless Wrought Steel Pipe | 2022 | ✗ | Pipe_Group, Schedule·두께 |
| `ASME_B16.5-2020_Pipe-Flanges-and-Flanged-Fittings.pdf` | ASME B16.5 Pipe Flanges and Flanged Fittings (NPS ½–24) | 2020 | ✓ | Flange_Group, Class_Rating(CL150–CL2500), P-T 등급 |
| `ASME_B16.9-2018_Factory-Made-Wrought-Buttwelding-Fittings.pdf` | ASME B16.9 Factory-Made Wrought Buttwelding Fittings | 2018 | ✓ | Wrought_Fitting_Group (LR/SR/3D 엘보, 티, 리듀서, 캡, 스터브엔드) |
| `ASME_B16.11-2016_Forged-Fittings-Socket-Welding-and-Threaded.pdf` | ASME B16.11 Forged Fittings, Socket-Welding and Threaded | 2016 | ✓ | Forged_Fitting_Group, Rating CL2000/3000/6000/9000 |
| `ASME_B16.20-2017_Metallic-Gaskets-for-Pipe-Flanges.pdf` | ASME B16.20 Metallic Gaskets for Pipe Flanges | 2017 | ✓ | Gasket_Group (Spiral Wound, Ring Joint, Jacketed) |
| `ASME_B16.20-2017_Metallic-Gaskets-for-Pipe-Flanges_scan.pdf` | 위와 같은 판의 스캔본 (중복) | 2017 | ✗ | — |
| `ASME_B16.10-2022_Face-to-Face-and-End-to-End-Dimensions-of-Valves.pdf` | ASME B16.10 Face-to-Face and End-to-End Dimensions of Valves | 2022 | ✗ | 밸브 그룹 (면간 치수) |
| `ASME_B16.34-2025_Valves-Flanged-Threaded-and-Welding-End.pdf` | ASME B16.34 Valves — Flanged, Threaded, and Welding End | 2025 | ✓ | 밸브 그룹 (압력-온도 등급) |
| `API_600-2021_Steel-Gate-Valves-Flanged-Butt-welding-Bolted-Bonnets.pdf` | API 600 Steel Gate Valves, 14th ed. | 2021 | ✓ | Gate_Valve_Group |
| `API_602-2015_Gate-Globe-Check-Valves-NPS4-and-Smaller.pdf` | API 602 Gate, Globe, Check Valves DN 100 and Smaller, 10th ed. | 2015 | ✓ | 소구경 단조 밸브 (Gate/Globe/Check). **Class 800** 근거: "not a listed class designation, but an intermediate class number widely used for socket welding and threaded end compact valves" (§1) |
| `API_594-2022_Check-Valves-Flanged-Lug-Wafer-Butt-welding.pdf` | API 594 Check Valves: Flanged, Lug, Wafer, Butt-welding, 9th ed. | 2022 | ✓ | Check_Valve_Group |
| `API_599-2002_Metal-Plug-Valves.pdf` | API 599 Metal Plug Valves, 5th ed. | 2002 | ✓ | Plug_Valve_Group |
| `MSS_SP-95-2018_Swaged-Nipples-and-Bull-Plugs.pdf` | MSS SP-95 Swage(d) Nipples and Bull Plugs | 2018 | ✗ | Swage (RCS/RES), Reducing_Table SN |

### vendor/ — 규격 원문이 아닌 업체 자료

| 파일 | 내용 |
|---|---|
| `vendor/Swage-Nipple-Dimension-Table_MSS-SP-95-2006.pdf` | MSS SP-95-2006 기준 스웨이지 니플 치수표 (업체 발췌) |
| `vendor/METLINE_Swage-Nipples-MSS-SP-95-Catalog.pdf` | METLINE 스웨이지 니플 카탈로그 |
