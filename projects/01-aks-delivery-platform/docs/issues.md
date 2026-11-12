# Issue backlog: AKS Delivery Platform

**Problem statement.** A team ships a small orders API to AKS by hand. Releases
are copied between environments with different commands, nobody approves
production changes, and a broken release stays live until someone notices.
The goal is one reusable pipeline that tests, builds, promotes the same image
through Dev, QA and Production, gates Production behind an approval, and rolls
back automatically when a post-deploy smoke test fails.

### ISSUE-1: Reusable multi-stage pipeline for build and AKS deployment
**Labels:** enhancement, ci-cd, azure-pipelines
**Status:** Done - [pipelines/azure-pipelines.yml](../pipelines/azure-pipelines.yml), [templates/](../pipelines/templates)

**Context.** Each environment had its own hand-written pipeline.

**Acceptance criteria**
- [x] One `azure-pipelines.yml` with Build, Deploy_Dev, Deploy_QA and Deploy_Prod stages.
- [x] Build and deploy logic lives in `templates/build.yml` and `templates/deploy-aks.yml` with typed parameters.
- [x] The image is built once and the same tag (`Build.BuildId`) is promoted to every environment.
- [x] Pull requests run tests only.

**Verification.** `python -m pytest tests` passes; YAML parses (`python -c "import yaml,sys;[yaml.safe_load(open(f)) for f in sys.argv[1:]]" pipelines/*.yml pipelines/templates/*.yml`). In Azure DevOps, a run on `main` shows four stages.

### ISSUE-2: Automatic rollback when the post-deploy smoke test fails
**Labels:** enhancement, reliability, helm
**Status:** Done - [scripts/deploy_with_rollback.sh](../scripts/deploy_with_rollback.sh), [scripts/smoke_test.py](../scripts/smoke_test.py), [tests/test_rollback_demo.py](../tests/test_rollback_demo.py)

**Context.** Liveness and readiness probes pass even when business endpoints return errors, so a bad release can go live.

**Acceptance criteria**
- [x] Smoke test checks `/healthz`, `/version` and two `/api/v1/orders` calls.
- [x] On failure the script runs `helm rollback` to the revision recorded before the upgrade.
- [x] The restored release is smoke-tested again and the stage still fails so later stages do not run.

**Verification.** `python scripts/local_release_demo.py` prints `SMOKE TEST FAILED`, then `ROLLBACK VERIFIED`, and ends with `DEMO RESULT: PASS`.

### ISSUE-3: Production approval and branch control
**Labels:** governance, azure-devops
**Status:** Documented - [docs/approvals.md](approvals.md) (needs an Azure DevOps project to apply)

**Acceptance criteria**
- [ ] `orders-prod` environment has an Approval check with a named approver group.
- [ ] `orders-qa` and `orders-prod` have Branch control limited to `refs/heads/main`.
- [ ] A run from a feature branch cannot reach Deploy_Prod.

**Verification.** Queue the pipeline from `main`; the Deploy_Prod stage shows "Waiting for approval". Queue from a feature branch; Deploy_Prod is skipped.

### ISSUE-4: Troubleshoot ImagePullBackOff after first deployment
**Labels:** bug, troubleshooting, aks, acr
**Status:** Runbook below

**Context.** First deployment to a new cluster shows pods in `ImagePullBackOff`.

**Acceptance criteria**
- [ ] Root cause identified from `kubectl describe pod` events.
- [ ] Cluster can pull from ACR without image pull secrets.

**Verification.**
```bash
kubectl -n orders-dev describe pod -l app.kubernetes.io/name=orders-api | grep -A3 Events
az aks check-acr -g rg-aks-delivery-lab -n aks-delivery-lab --acr <acr>.azurecr.io
az aks update -g rg-aks-delivery-lab -n aks-delivery-lab --attach-acr <acr>   # fix if check fails
```

### ISSUE-5: Improvement - progressive delivery with canary analysis
**Labels:** enhancement, improvement, reliability
**Status:** Open

**Context.** Rollback happens after all pods run the new version. A canary would limit exposure.

**Acceptance criteria**
- [ ] Deploy the new version to one replica behind the same Service first.
- [ ] Promote only if the error rate stays under 1% for 5 minutes (Prometheus query).
- [ ] Document the trade-off against the current rollback-only approach.

**Verification.** Repeat the defect demo; only canary traffic sees HTTP 500 and promotion is blocked.

## Import into GitHub

```bash
# from the repository root, after the GitHub repository exists
python tools/import_issues.py projects/01-aks-delivery-platform/docs/issues.md --repo gollapudisrinu18/my-profile --dry-run
python tools/import_issues.py projects/01-aks-delivery-platform/docs/issues.md --repo gollapudisrinu18/my-profile
```
