# Demo: Azure Hub-and-Spoke Infrastructure with Terraform

**Format:** Captioned MP4 screen recording of the browser walkthrough, plus the walkthrough itself

- Browser walkthrough (captioned, keyboard accessible): https://gollapudisrinu18.github.io/my-profile/demos/azure-hub-spoke-terraform.html
- Video (MP4, captions in WebVTT): https://gollapudisrinu18.github.io/my-profile/assets/video/azure-hub-spoke-terraform.mp4
- Run it yourself: `python tools/dns_incident_demo.py` from `projects/02-azure-hub-spoke-terraform`

## Recording script

| Scene | Show on screen | Caption |
|---|---|---|
| 1 | Title card | A missing private DNS zone link sends traffic to the public endpoint. Terraform fixes it. |
| 2 | Diagram: Network view | Network view |
| 3 | Diagram: Name resolution: broken vs fixed | Name resolution: broken vs fixed |
| 4 | Terminal: 1. Broken state: terraform apply -var-file=misconfig.tfvars | Broken state: the app spoke follows the public CNAME and gets a public IP, so the private endpoint is bypassed and storage returns 403. |
| 5 | Terminal: 2. Diagnose: compare with a VNet that works | The data spoke works. Comparing the two shows the privatelink.blob zone is linked to hub and data only. |
| 6 | Terminal: 3. Fix: link the app spoke (terraform apply without misconfig.tfvars) | Terraform adds the missing VNet link. The same lookup from the app spoke now returns the private endpoint IP. |
| 7 | Terminal: Result | The check expected a private answer and now passes. |
| 8 | Result card | With misconfig.tfvars the app spoke resolves storage to a public IP (expected private: FAIL). Linking the zone through Terraform returns the private endpoint 10.1.2.4 (PASS). |

## Captured output

The walkthrough uses this output, captured from a real run by `tools/capture_demos.py`:

```text
$ python tools/dns_incident_demo.py

=== 1. Broken state: terraform apply -var-file=misconfig.tfvars ===
Symptom reported: app in spoke 'app' gets HTTP 403 AuthorizationFailure from blob storage
Resolving sthslabdemo01.blob.core.windows.net from VNet 'app'
  sthslabdemo01.blob.core.windows.net -> CNAME sthslabdemo01.privatelink.blob.core.windows.net (public DNS)
  zone privatelink.blob.core.windows.net is NOT linked to VNet 'app'; Azure DNS falls back to public resolution
  sthslabdemo01.privatelink.blob.core.windows.net -> A 20.60.0.10 (public endpoint)
RESULT: public IP 20.60.0.10 - private endpoint bypassed; storage has public access disabled, so requests fail with HTTP 403
CHECK: expected private -> FAIL

=== 2. Diagnose: compare with a VNet that works ===
Resolving sthslabdemo01.blob.core.windows.net from VNet 'data'
  sthslabdemo01.blob.core.windows.net -> CNAME sthslabdemo01.privatelink.blob.core.windows.net (public DNS)
  sthslabdemo01.privatelink.blob.core.windows.net -> A 10.1.2.4 (private zone privatelink.blob.core.windows.net, linked to 'data')
RESULT: private endpoint 10.1.2.4 - traffic stays on the VNet

Diagnosis: the privatelink.blob zone has links for hub and data only.
On Azure: az network private-dns link vnet list -g rg-hslab-network -z privatelink.blob.core.windows.net -o table

=== 3. Fix: link the app spoke (terraform apply without misconfig.tfvars) ===
  + module.blob_dns.azurerm_private_dns_zone_virtual_network_link.this["app"]
Resolving sthslabdemo01.blob.core.windows.net from VNet 'app'
  sthslabdemo01.blob.core.windows.net -> CNAME sthslabdemo01.privatelink.blob.core.windows.net (public DNS)
  sthslabdemo01.privatelink.blob.core.windows.net -> A 10.1.2.4 (private zone privatelink.blob.core.windows.net, linked to 'app')
RESULT: private endpoint 10.1.2.4 - traffic stays on the VNet
CHECK: expected private -> PASS

=== Result ===
DEMO RESULT: PASS - app spoke now resolves the private endpoint
```
