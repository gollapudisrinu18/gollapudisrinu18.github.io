# Runbook: restore the orders archive after data loss

**Targets:** RTO 30 minutes, RPO 60 minutes. **Owner:** platform on-call.

1. **Confirm the loss.** `az storage blob list --account-name <sa> -c orders --auth-mode login --query 'length(@)'` or the deletion alert (`Delete Blob` count > 10 in 5 min from the storage diagnostic logs).
2. **Stop the bleeding.** Pause the job or identity that deleted data (check `StorageBlobLogs` in Log Analytics for the caller). Do not write new data to the container yet.
3. **Pick the restore point.** Latest time before the first delete:
   ```kusto
   StorageBlobLogs
   | where OperationName == "DeleteBlob" and AccountName == "<sa>"
   | summarize first_delete = min(TimeGenerated)
   ```
4. **Get approval** from the incident commander (record the time; it counts towards RTO).
5. **Restore.**
   - Blob PITR: `az storage blob restore -g <rg> -n <sa> --time-to-restore <ISO time>`
   - Soft-deleted single blobs: `az storage blob undelete --account-name <sa> -c orders -n <blob> --auth-mode login`
6. **Replay the gap.** Re-publish orders written after the restore point from the order queue or source system.
7. **Verify.** Download and run `python dr/verify_dir.py --dir <downloaded> --manifest <manifest.json>`; record count matches.
8. **Record** RTO (loss detected → verified) and RPO (incident → restore point) in a drill report.

## Drill schedule
Run `dr/drill.py` monthly and `scripts/azure-drill.sh` quarterly. File the generated report in `docs/`.
