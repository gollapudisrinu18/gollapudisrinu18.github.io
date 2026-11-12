# Demo: Azure Disaster Recovery and Restore Drill

**Format:** Captioned MP4 screen recording of the browser walkthrough, plus the walkthrough itself

- Browser walkthrough (captioned, keyboard accessible): https://gollapudisrinu18.github.io/my-profile/demos/azure-dr-restore-drill.html
- Video (MP4, captions in WebVTT): https://gollapudisrinu18.github.io/my-profile/assets/video/azure-dr-restore-drill.mp4
- Run it yourself: `python dr/drill.py` from `projects/06-azure-dr-restore-drill`

## Recording script

| Scene | Show on screen | Caption |
|---|---|---|
| 1 | Title card | Data is deleted on purpose, restored, and proven complete. |
| 2 | Diagram: Architecture | Architecture |
| 3 | Terminal: 1. Prepare synthetic dataset and scheduled backup | A synthetic dataset is backed up; 37 more orders arrive after the backup. |
| 4 | Terminal: 2. Incident: primary dataset deleted | The primary dataset is deleted and the integrity check fails. |
| 5 | Terminal: 3. Restore latest backup and verify | The latest backup is restored and every file checksum matches the manifest. |
| 6 | Terminal: 4. Measured against targets | RTO and RPO are measured against their targets and a drill report is written. |
| 7 | Result card | 1,000 of 1,037 records restored with all checksums matching; the 37 records written after the backup are the measured RPO loss. RTO 7 minutes against a 30-minute target, RPO 45 minutes against 60. |

## Captured output

The walkthrough uses this output, captured from a real run by `tools/capture_demos.py`:

```text
$ python dr/drill.py
=== 1. Prepare synthetic dataset and scheduled backup ===
  backup 20261112T105558Z: 20 files, 1000 records
  37 orders written in the 45 min after the backup; primary now has 1037

=== 2. Incident: primary dataset deleted ===
  integrity check: FAILED (20 problems, e.g. missing orders-000.json)

=== 3. Restore latest backup and verify ===
  restored 20261112T105558Z in 0.00 s
  checksum verification: PASS (20 files)
  records restored: 1000 of 1037 (lost: 37)

=== 4. Measured against targets ===
  RTO 7.0 min (target 30) -> MET
  RPO 45 min / 37 records (target 60 min) -> MET

Wrote docs/drill-report.md
DEMO RESULT: PASS - data restored, checksums verified, RTO and RPO met
```
