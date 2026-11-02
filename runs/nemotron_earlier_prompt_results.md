# Results (15 synthetic invoices)

Keyword baseline correct: 11/15

LLM label correct: 14/15

Contested cases flagged for review: 5/5

Wrong AND would auto-post (worst failure): none

Sent to review: 9/15 (so contested recall alone proves little)

Non-contested sent to review: 4/10

Invoices per review trigger: {'contested': 8, 'differs from CA-approved history': 1, 'exposure': 2, 'low confidence': 1, 'model abstained': 1}

Median share of invoice quoted as evidence: 99%


| id | expected | baseline | llm | act | section | tds | route reasons |
|---|---|---|---|---|---|---|---|
| INV01 | contract_work | contract_work | contract_work | 2025 | 393(1) Table Sl. 6(i) | 1700 | - |
| INV02 | professional_fees | professional_fees | professional_fees | 2025 | 393(1) Table Sl. 6(iii) | 25000 | - |
| INV03 | contract_work | contract_work | contract_work | 2025 | 393(1) Table Sl. 6(i) | 1280 | contested: contract_work/technical_services |
| INV04 | contract_work | technical_services | contract_work | 2025 | 393(1) Table Sl. 6(i) | 9600 | contested: contract_work/technical_services |
| INV05 | contract_work | technical_services | contract_work | 2025 | 393(1) Table Sl. 6(i) | 3600 | contested: contract_work/technical_services |
| INV06 | professional_fees | professional_fees | professional_fees | 2025 | 393(1) Table Sl. 6(iii) | 6000 | - |
| INV07 | contract_work | rent_plant_machinery | contract_work | 2025 | 393(1) Table Sl. 6(i) | 720 | contested: contract_work/rent_plant_machinery |
| INV08 | rent_plant_machinery | rent_plant_machinery | rent_plant_machinery | 2025 | 393(1) Table Sl. 2(ii) | 1800 | contested: rent_plant_machinery/contract_work |
| INV09 | rent_land_building | rent_land_building | rent_land_building | 2025 | 393(1) Table Sl. 2(ii) | 12000 | - |
| INV10 | commission | commission | commission | 2025 | 393(1) Table Sl. 1(ii) | 900 | - |
| INV11 | unclear | unclear | unclear | - | - | - | model abstained; low confidence |
| INV12 | contract_work | contract_work | contract_work | 2025 | 393(1) Table Sl. 6(i) | 6000 | contested: contract_work/professional_fees; exposure Rs 24,000 |
| INV13 | professional_fees | unclear | professional_fees | 1961 | 194J(b) | 7500 | contested: professional_fees/technical_services |
| INV14 | technical_services | technical_services | contract_work | 2025 | 393(1) Table Sl. 6(i) | 3000 | contested: contract_work/professional_fees; contested: contract_work/technical_services; exposure Rs 12,000; differs from CA-approved history (technical_services) |
| INV15 | contract_work | contract_work | contract_work | 2025 | 393(1) Table Sl. 6(i) | 0 | - |
