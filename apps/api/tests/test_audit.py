from uuid import uuid4
import zipfile
from io import BytesIO

from apps.api.app.audit import AuditLog, AuditOutcome, AuditRecord, export_csv, export_pdf, export_xlsx


def records():
    organization_id = uuid4()
    target_id = uuid4()
    log = AuditLog()
    log.append(AuditRecord(organization_id=organization_id, actor_type="system", action="inventory.updated", target_id=target_id, outcome=AuditOutcome.succeeded))
    log.append(AuditRecord(organization_id=organization_id, actor_type="user", action="job.created", target_id=target_id, outcome=AuditOutcome.accepted))
    return log, organization_id, target_id


def test_audit_is_hash_chained_searchable_and_timeline_ordered():
    log, organization_id, target_id = records()
    assert log.verify_integrity()
    assert len(log.search(organization_id, action="job.created")) == 1
    assert len(log.timeline(organization_id, target_id)) == 2
    log._records[0].action = "tampered"
    assert not log.verify_integrity()


def test_audit_exports_are_nonempty_csv_xlsx_and_pdf():
    log, organization_id, _ = records()
    selected = log.search(organization_id)
    assert b"action" in export_csv(selected)
    workbook = export_xlsx(selected)
    with zipfile.ZipFile(BytesIO(workbook)) as archive:
        assert "_rels/.rels" in archive.namelist()
        assert "xl/workbook.xml" in archive.namelist()
        assert "xl/_rels/workbook.xml.rels" in archive.namelist()
        assert "xl/worksheets/sheet1.xml" in archive.namelist()
    assert export_pdf(selected).startswith(b"%PDF")
