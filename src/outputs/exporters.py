import csv
import json
from typing import List, Dict, Any

from openpyxl import Workbook

FIELDS = [
    "jobTitle",
    "companyName",
    "location",
    "jobUrl",
    "jobDescription",
    "salary",
    "employmentType",
    "datePosted",
    "category",
    "experienceLevel",
    "source",
]

def _ordered(record: Dict[str, Any]) -> Dict[str, Any]:
    return {k: record.get(k, "") for k in FIELDS}

def export_json(records: List[Dict[str, Any]], path: str) -> None:
    ordered = [_ordered(r) for r in records]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=2)

def export_csv(records: List[Dict[str, Any]], path: str) -> None:
    ordered = [_ordered(r) for r in records]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in ordered:
            writer.writerow(row)

def export_excel(records: List[Dict[str, Any]], path: str) -> None:
    ordered = [_ordered(r) for r in records]
    wb = Workbook()
    ws = wb.active
    ws.title = "Jobs"

    ws.append(FIELDS)
    for row in ordered:
        ws.append([row.get(k, "") for k in FIELDS])
    wb.save(path)