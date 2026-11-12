# Issue backlog: Azure Hub-and-Spoke Infrastructure with Terraform

**Problem statement.** Application teams create their own VNets by hand. Address
ranges overlap, NSG rules drift, and private endpoints are added without the
matching private DNS links, so services silently fall back to public endpoints
and fail. The goal is a set of reusable Terraform modules for a hub-and-spoke
network with private endpoints and private DNS, kept in remote state and
validated before every change.

### ISSUE-1: Reusable modules for hub, spokes, peering, NSGs, private endpoints and private DNS
**Labels:** enhancement, terraform, networking
**Status:** Done - [modules/](../modules), [envs/lab/main.tf](../envs/lab/main.tf)

**Acceptance criteria**
- [x] Six modules, each with `main.tf`, `variables.tf` and `outputs.tf`.
- [x] Peering module creates both directions.
- [x] Private DNS zone links are driven by a map so links cannot be forgotten silently.
- [x] Storage account has public network access disabled and is reached through a private endpoint.

**Verification.** `python tools/validate_tf.py` passes. In CI: `terraform fmt -check -recursive`, `terraform validate` and `terraform test` pass.

### ISSUE-2: Remote state with Entra ID authentication
**Labels:** enhancement, terraform, security
**Status:** Done - [bootstrap/remote-state.sh](../bootstrap/remote-state.sh), [envs/lab/backend.tf](../envs/lab/backend.tf)

**Acceptance criteria**
- [x] State stored in a dedicated storage account with blob versioning and soft delete.
- [x] Backend uses `use_azuread_auth = true`; no storage keys in files.
- [x] `terraform init -backend=false` still works for offline validation.

**Verification.** `bash bootstrap/remote-state.sh`, then `terraform init -backend-config=backend.hcl` succeeds and `az storage blob list --account-name <sa> -c tfstate --auth-mode login` shows `hub-spoke-lab.tfstate` after apply.

### ISSUE-3: App spoke resolves storage to a public IP (HTTP 403)
**Labels:** bug, troubleshooting, dns, private-link
**Status:** Fixed - reproduced with [envs/lab/misconfig.tfvars](../envs/lab/misconfig.tfvars), diagnosed with [tools/dns_check.py](../tools/dns_check.py), covered by [tests/test_dns_and_static.py](../tests/test_dns_and_static.py)

**Context.** Workloads in the app spoke get `AuthorizationFailure` (403) from blob storage while the data spoke works.

**Acceptance criteria**
- [x] Root cause identified: `privatelink.blob.core.windows.net` is not linked to the app spoke.
- [x] Fix applied through Terraform, not the portal.
- [x] Resolution from the app spoke returns the private endpoint IP.

**Verification.** `python tools/dns_incident_demo.py` ends with `DEMO RESULT: PASS`. On Azure: `bash tools/verify-on-azure.sh` shows `Address: 10.1.2.x` for the storage FQDN.

### ISSUE-4: Plan-time guardrails for names, CIDRs and NSG priorities
**Labels:** enhancement, terraform, quality
**Status:** Done - validation blocks in `variables.tf`, test in [envs/lab/tests/lab.tftest.hcl](../envs/lab/tests/lab.tftest.hcl)

**Acceptance criteria**
- [x] Invalid CIDR, prefix or NSG priority fails at plan time with a clear message.
- [x] `terraform test` includes an `expect_failures` case.

**Verification.** `terraform test` in `envs/lab` reports 3 passed runs.

### ISSUE-5: Improvement - central DNS with Azure DNS Private Resolver in the hub
**Labels:** enhancement, improvement, dns
**Status:** Open

**Context.** Linking every zone to every spoke does not scale and does not help on-premises clients.

**Acceptance criteria**
- [ ] Add a DNS Private Resolver inbound endpoint in the hub.
- [ ] Spokes use the resolver IP as custom DNS; zones are linked to the hub only.
- [ ] `dns_check.py` model supports forwarding through the hub.

**Verification.** `nslookup` from both spokes and from a simulated on-premises forwarder returns private IPs.

## Import into GitHub

```bash
python tools/import_issues.py projects/02-azure-hub-spoke-terraform/docs/issues.md --repo gollapudisrinu18/my-profile --dry-run
python tools/import_issues.py projects/02-azure-hub-spoke-terraform/docs/issues.md --repo gollapudisrinu18/my-profile
```
