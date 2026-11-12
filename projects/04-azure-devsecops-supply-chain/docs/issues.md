# Issue backlog: Azure DevSecOps Software Supply Chain

**Problem statement.** Images reach AKS straight from developer builds. Nobody
can say which packages are inside a running image, vulnerable base images are
found only after release, and any image that can be pulled can run. The goal is
a pipeline that scans, records an SBOM, signs with a key held in Azure Key
Vault, and a cluster that refuses anything unsigned, with workloads reading
secrets through Microsoft Entra Workload ID instead of stored credentials.

### ISSUE-1: Scan, SBOM, sign and verify in Azure Pipelines
**Labels:** enhancement, devsecops, azure-pipelines
**Status:** Done - [pipelines/azure-pipelines.yml](../pipelines/azure-pipelines.yml)

**Acceptance criteria**
- [x] Trivy `fs` scan for secrets and Dockerfile misconfiguration before build.
- [x] Image pushed and referenced by digest from then on.
- [x] Trivy image scan fails on fixable HIGH/CRITICAL findings; exceptions go in `.trivyignore` with a reason.
- [x] Syft SPDX SBOM published as a pipeline artifact and attached with `cosign attest`.
- [x] `cosign sign` uses `azurekms://`; `cosign verify` runs before deploy.

**Verification.** In Azure DevOps, the Sign stage log ends with `Signed and verified <acr>/supplychain/demo-app@sha256:...`. `cosign tree <image>` shows a signature and an SBOM attestation.

### ISSUE-2: Reject unsigned images at admission
**Labels:** enhancement, security, kubernetes
**Status:** Done - [policy/kyverno/verify-image-signatures.yaml](../policy/kyverno/verify-image-signatures.yaml), local equivalent [admission/webhook.py](../admission/webhook.py), tests [tests/test_supply_chain.py](../tests/test_supply_chain.py)

**Acceptance criteria**
- [x] Unsigned image from the protected repository is rejected with a clear reason.
- [x] Signed image is admitted and pinned to its digest.
- [x] Tag-only references and signatures for a different digest are rejected.
- [x] Images outside the protected repository are not affected.

**Verification.** `python admission/demo.py` ends with `DEMO RESULT: PASS`. On AKS: `kubectl apply -f policy/test-pods.yaml` creates `signed-test` and rejects `unsigned-test`.

### ISSUE-3: Read secrets with Workload ID instead of stored credentials
**Labels:** enhancement, security, entra-id, key-vault
**Status:** Done (needs Azure to run) - [workload-identity/](../workload-identity)

**Acceptance criteria**
- [x] User-assigned identity federated to `system:serviceaccount:supplychain:demo-app`.
- [x] Identity has only `Key Vault Secrets User` on the vault.
- [x] Secret mounted at `/mnt/secrets/app-db-password` through the Secrets Store CSI driver.

**Verification.** `kubectl -n supplychain exec deploy/demo-app -- ls /mnt/secrets` lists `app-db-password`; `curl` to `/` returns `"secret_mounted": true`.

### ISSUE-4: Troubleshoot - Kyverno cannot fetch signatures from ACR
**Labels:** bug, troubleshooting, kyverno, acr
**Status:** Runbook

**Context.** Signed pods are rejected with `failed to verify image ... UNAUTHORIZED`.

**Acceptance criteria**
- [ ] Kyverno can read signature tags from ACR.

**Verification.**
```bash
kubectl -n kyverno logs deploy/kyverno-admission-controller | grep -i unauthorized
# Option A: give the kubelet identity AcrPull and configure Kyverno's imagePullSecrets / registry credential helper
# Option B: create a pull secret and set --imagePullSecrets on the Kyverno deployment
kubectl apply -f policy/test-pods.yaml   # signed-test should now be admitted
```

### ISSUE-5: Improvement - keyless signing and SBOM policy checks
**Labels:** enhancement, improvement, devsecops
**Status:** Open

**Acceptance criteria**
- [ ] Evaluate Notation with Azure Key Vault plugin as the ACR-native alternative to Cosign.
- [ ] Add a Kyverno rule that requires an SPDX attestation, not only a signature.
- [ ] Block images whose SBOM lists a package on a deny list.

**Verification.** A signed image without an SBOM attestation is rejected.

## Import into GitHub

```bash
python tools/import_issues.py projects/04-azure-devsecops-supply-chain/docs/issues.md --repo gollapudisrinu18/my-profile --dry-run
python tools/import_issues.py projects/04-azure-devsecops-supply-chain/docs/issues.md --repo gollapudisrinu18/my-profile
```
