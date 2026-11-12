# Verification results

Checked in the build workspace on 12 Nov 2026 (Python 3.13, Node 22, Chrome, Playwright, ffmpeg, Mermaid CLI). Terraform, Helm, promtool, the Azure CLI, Docker and a Kubernetes cluster were not available there; those checks run in GitHub Actions CI (`.github/workflows/ci.yml`) or need an Azure subscription.

## Six-project table

| Project | Passed locally | Runs in CI after push | Still needs Azure / external access |
|---|---|---|---|
| AKS Delivery Platform | 7 pytest tests; demo: 1.1.0 fails smoke test, rolled back to 1.0.0 (revision 3), `DEMO RESULT: PASS`; pipeline + values YAML parse; deploy script `bash -n` | `helm lint`, `helm template` for dev/qa/prod | ACR build, AKS deploy, environment approval, rollback on a real cluster |
| Hub-and-Spoke Terraform | 7 pytest tests; static Terraform checks; DNS incident demo: broken → FAIL, fixed → private IP 10.1.2.4, `DEMO RESULT: PASS` | `terraform validate`, `terraform test` (3 runs with mocked provider), `terraform fmt` (advisory) | `terraform apply`, remote state, `nslookup` from a VM in the spoke |
| Observability & SRE Incident Lab | 8 pytest tests; live demo against the real instrumented service: burn rate 0x → over 14.4x → 0x, cause `inventory.lookup`, `DEMO RESULT: PASS`; simulation: detect 16 min, mitigate 27 min, 3.6% budget; postmortem numbers checked against the simulation | `promtool check rules`, `promtool test rules` | Docker Compose stack, Azure managed Prometheus, Managed Grafana, Log Analytics, App Insights |
| DevSecOps Supply Chain | 9 pytest tests; real ECDSA signing in Cosign's payload format; webhook over HTTP: unsigned / tag-only / tampered rejected, signed admitted, `DEMO RESULT: PASS`; all YAML parses | (same tests) | Trivy, Syft and Cosign in Azure Pipelines, Key Vault key, Kyverno on AKS, Workload ID mount |
| Functions Event Processing | 19 pytest tests (in-memory and SQLite stores); local queue runtime: ORD-1 delivered 3 times, recorded once; retry, poison after 5 dequeues, `DEMO RESULT: PASS` | (same tests) | `func start` with Azurite, Function App, Table Storage idempotency |
| DR Restore Drill | 4 pytest tests; drill: 1,000/1,037 records restored, all checksums match, RTO 7.0 min vs 30, RPO 45 min vs 60, `DEMO RESULT: PASS` | (same tests) | Blob point-in-time restore with `scripts/azure-drill.sh` |

## Website, diagrams, demos and voice assistant

| Check | Result |
|---|---|
| Site build | 42 files: home, 6 case studies, 6 demo walkthroughs, 404, knowledge base (25 entries) |
| Mermaid diagrams | 16/16 render (10 used on the site as SVG; all README/architecture blocks checked) |
| Internal links and images | All resolve (browser test) |
| Diagrams load in the browser | All 6 case studies, flagship pages show 2 diagrams |
| Demo videos | 6 MP4 files (H.264, 1280×720, 40–50 s, ~300 KB each), full decode with 0 errors, WebVTT captions |
| Walkthroughs | Play/pause, back/next, ←/→ keys, captions announced with `aria-live` |
| Keyboard and mobile | Skip link gets focus first; mobile menu opens and closes; layouts checked at 390 px and 1366 px |
| Reduced motion | `prefers-reduced-motion` disables smooth scroll and animations |
| Assistant matching (Node) | 17/17: sample questions, Telugu questions, unavailable answers, links resolve, no phone or email in the knowledge base |
| Assistant in Chrome (Playwright) | Text input; answer labels (career / lab / simulated incident); unavailable answer; no voice support → mic disabled with message; microphone denied → error message, typing still works; listening status and Stop; spoken question answered and read aloud (en-US); Telugu input (te-IN) and Telugu playback; Telugu with no Telugu voice → text only; nothing starts before a click; nothing saved to localStorage, sessionStorage or cookies |
| Real Chrome speech API | With microphone permission not granted, Chrome's own `webkitSpeechRecognition` returned `not-allowed` and the page showed the denied message |

### Voice checks I could not complete here
- Speaking into a real microphone and hearing real audio output. The sandbox has no microphone or speakers. The browser speech APIs were exercised with controlled stand-ins, plus one real-API permission-denied run.
- Whether a given recruiter's browser has a Telugu voice installed. The site detects this and falls back to text.

## Publishing
The repository is committed locally. Pushing to GitHub, enabling Pages and checking the live URLs need GitHub access. The final resume links are added only after the live site responds.
