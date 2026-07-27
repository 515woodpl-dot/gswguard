from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime
from enum import StrEnum
from typing import Iterable
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


class AuditOutcome(StrEnum):
    accepted = "accepted"
    succeeded = "succeeded"
    failed = "failed"
    denied = "denied"


class AuditRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    actor_type: str = Field(pattern=r"^(user|device|system)$")
    actor_id: UUID | None = None
    action: str = Field(min_length=1, max_length=120)
    target_type: str | None = None
    target_id: UUID | None = None
    outcome: AuditOutcome
    reason: str | None = Field(default=None, max_length=500)
    correlation_id: UUID | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    previous_hash: str = ""
    event_hash: str = ""


class AuditLog:
    """Append-only test implementation of the server-side audit adapter."""

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def append(self, record: AuditRecord) -> AuditRecord:
        previous = self._records[-1].event_hash if self._records else "GENESIS"
        payload = record.model_dump(mode="json", exclude={"previous_hash", "event_hash"})
        event_hash = hashlib.sha256((previous + json.dumps(payload, sort_keys=True)).encode()).hexdigest()
        finalized = record.model_copy(update={"previous_hash": previous, "event_hash": event_hash})
        self._records.append(finalized)
        return finalized

    def search(self, organization_id: UUID, action: str | None = None, outcome: AuditOutcome | None = None) -> list[AuditRecord]:
        return [
            record for record in self._records
            if record.organization_id == organization_id
            and (action is None or record.action == action)
            and (outcome is None or record.outcome == outcome)
        ]

    def timeline(self, organization_id: UUID, target_id: UUID) -> list[AuditRecord]:
        return sorted(
            [record for record in self._records if record.organization_id == organization_id and record.target_id == target_id],
            key=lambda record: record.created_at,
        )

    def verify_integrity(self) -> bool:
        previous = "GENESIS"
        for record in self._records:
            payload = record.model_dump(mode="json", exclude={"previous_hash", "event_hash"})
            expected = hashlib.sha256((previous + json.dumps(payload, sort_keys=True)).encode()).hexdigest()
            if record.previous_hash != previous or record.event_hash != expected:
                return False
            previous = record.event_hash
        return True


def export_csv(records: Iterable[AuditRecord]) -> bytes:
    output = io.StringIO()
    fields = ["id", "organization_id", "actor_type", "action", "outcome", "target_id", "reason", "created_at", "event_hash"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for record in records:
        data = record.model_dump(mode="json")
        writer.writerow({field: data.get(field, "") for field in fields})
    return output.getvalue().encode("utf-8")


def export_xlsx(records: Iterable[AuditRecord]) -> bytes:
    rows = [["id", "organization_id", "actor_type", "action", "outcome", "target_id", "reason", "created_at", "event_hash"]]
    for record in records:
        data = record.model_dump(mode="json")
        rows.append([data.get(field, "") for field in rows[0]])
    def cells(row: list[str]) -> str:
        return "<row>" + "".join(f'<c t="inlineStr"><is><t>{str(value).replace("&", "&amp;").replace("<", "&lt;")}</t></is></c>' for value in row) + "</row>"
    sheet = "<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><sheetData>" + "".join(cells(row) for row in rows) + "</sheetData></worksheet>"
    content_types = "<?xml version=\"1.0\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"xml\" ContentType=\"application/xml\"/><Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/></Types>"
    workbook = "<?xml version=\"1.0\"?><workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><sheets><sheet name=\"Audit\" sheetId=\"1\" r:id=\"rId1\"/></sheets></workbook>"
    rels = "<?xml version=\"1.0\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/></Relationships>"
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return result.getvalue()


def export_pdf(records: Iterable[AuditRecord]) -> bytes:
    result = io.BytesIO()
    document = canvas.Canvas(result, pagesize=letter)
    width, height = letter
    y = height - 40
    document.setFont("Helvetica", 9)
    document.drawString(40, y, "YorGuard audit export")
    y -= 24
    for record in records:
        line = f"{record.created_at.isoformat()} | {record.action} | {record.outcome.value} | {record.event_hash[:12]}"
        document.drawString(40, y, line[:120])
        y -= 14
        if y < 40:
            document.showPage()
            document.setFont("Helvetica", 9)
            y = height - 40
    document.save()
    return result.getvalue()
