# Issue backlog: Azure Disaster Recovery and Restore Drill

**Problem statement.** The orders archive has "backups", but nobody has
restored from them, the RTO and RPO were never measured, and there is no way to
prove a restore is complete. The goal is a repeatable drill with synthetic data
that deletes the data on purpose, restores it, proves integrity with checksums,
and reports measured RTO and RPO against targets.

### ISSUE-1: Repeatable local backup and restore drill
**Labels:** enhancement, disaster-recovery
**Status:** Done - [dr/drill.py](../dr/drill.py), [dr/drlib.py](../dr/drlib.py), [tests/test_drill.py](../tests/test_drill.py)

**Acceptance criteria**
- [x] Deterministic synthetic dataset; no real data.
- [x] Backups are read-only snapshots with a SHA-256 manifest and record count.
- [x] Drill simulates deletion, restores the latest backup and verifies every file.
- [x] Report written to `docs/drill-report.md` with RTO and RPO against targets.

**Verification.** `python dr/drill.py` ends with `DEMO RESULT: PASS`; see [drill-report.md](drill-report.md).

### ISSUE-2: Blob point-in-time restore on Azure
**Labels:** enhancement, azure-storage
**Status:** Done (needs Azure to run) - [scripts/azure-drill.sh](../scripts/azure-drill.sh)

**Acceptance criteria**
- [x] Versioning, change feed, soft delete (14 d) and restore policy (7 d) enabled.
- [x] Script deletes all blobs, restores to a recorded point and verifies with the same manifest.

**Verification.** Script prints `INTEGRITY PASS` and the measured restore time.

### ISSUE-3: Troubleshoot - PITR fails with "restore policy not enabled"
**Labels:** bug, troubleshooting
**Status:** Runbook

**Acceptance criteria**
- [ ] Explain that PITR needs versioning, change feed and a delete retention longer than the restore window.
- [ ] Fix applied with `blob-service-properties update`.

**Verification.** `az storage account blob-service-properties show -g <rg> -n <sa> --query restorePolicy` shows `enabled: true`.

### ISSUE-4: Runbook with measured RTO/RPO definitions
**Labels:** documentation, sre
**Status:** Done - [docs/runbook.md](runbook.md)

**Acceptance criteria**
- [x] Steps from detection to verification, including how to find the restore point with KQL.
- [x] Replay step for data written after the restore point.

**Verification.** A second engineer can run the drill from the runbook alone.

### ISSUE-5: Improvement - cross-region copy for regional outages
**Labels:** enhancement, improvement, disaster-recovery
**Status:** Open

**Acceptance criteria**
- [ ] Object replication to a storage account in a paired region.
- [ ] Drill variant that restores from the secondary account.

**Verification.** Drill report shows RTO/RPO for the regional scenario.

## Import into GitHub

```bash
python tools/import_issues.py projects/06-azure-dr-restore-drill/docs/issues.md --repo gollapudisrinu18/my-profile --dry-run
python tools/import_issues.py projects/06-azure-dr-restore-drill/docs/issues.md --repo gollapudisrinu18/my-profile
```
