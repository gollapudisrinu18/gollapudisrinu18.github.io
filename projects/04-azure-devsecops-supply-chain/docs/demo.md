# Demo: Azure DevSecOps Software Supply Chain

**Format:** Captioned MP4 screen recording of the browser walkthrough, plus the walkthrough itself

- Browser walkthrough (captioned, keyboard accessible): https://gollapudisrinu18.github.io/my-profile/demos/azure-devsecops-supply-chain.html
- Video (MP4, captions in WebVTT): https://gollapudisrinu18.github.io/my-profile/assets/video/azure-devsecops-supply-chain.mp4
- Run it yourself: `python admission/demo.py` from `projects/04-azure-devsecops-supply-chain`

## Recording script

| Scene | Show on screen | Caption |
|---|---|---|
| 1 | Title card | Only images signed with the Key Vault key may run. A harmless unsigned image is turned away at admission. |
| 2 | Diagram: Pipeline and runtime view | Pipeline and runtime view |
| 3 | Diagram: Admission sequence | Admission sequence |
| 4 | Terminal: 1. Generate signing key (ECDSA P-256) | An ECDSA P-256 signing key is created. In the pipeline this key lives in Azure Key Vault. |
| 5 | Terminal: 2. Build two harmless test images | Two harmless synthetic images are built and identified by digest. |
| 6 | Terminal: 3. Sign the release image | Only the release image is signed, and the signature verifies. |
| 7 | Terminal: 4. Admission decisions | Admission decisions: the unsigned, tag-only and tampered images are rejected; the signed image is admitted. |
| 8 | Result card | Unsigned test image: rejected. Signed image: admitted. Tag-only reference and a signature copied to another digest: rejected. Images outside the protected repository: unaffected. |

## Captured output

The walkthrough uses this output, captured from a real run by `tools/capture_demos.py`:

```text
$ python admission/demo.py
=== 1. Generate signing key (ECDSA P-256) ===
  public key fingerprint: sha256:05ae351fc39bad32...

=== 2. Build two harmless test images ===
  acrportfolio.azurecr.io/supplychain/demo-app@sha256:1099df7c5fb8...  (will be signed)
  acrportfolio.azurecr.io/supplychain/demo-app@sha256:bb041240ec25...  (not signed)

=== 3. Sign the release image ===
  cosign-style verify: Verified OK

=== 4. Admission decisions ===
  unsigned-pod     -> REJECTED: acrportfolio.azurecr.io/supplychain/demo-app@sha256:bb041240ec25...: no signature found - image is unsigned
  signed-pod       -> ADMITTED: signature verified for all protected images
  tag-only-pod     -> REJECTED: acrportfolio.azurecr.io/supplychain/demo-app:1.0.0: protected images must be referenced by digest (@sha256:...)
  tampered-pod     -> REJECTED: acrportfolio.azurecr.io/supplychain/demo-app@sha256:8c42834369d1...: signature was made for a different digest
  unprotected-pod  -> ADMITTED: no images from protected registries

DEMO RESULT: PASS - unsigned image rejected, signed image admitted
```
