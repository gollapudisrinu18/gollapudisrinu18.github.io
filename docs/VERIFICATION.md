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

## Portfolio redesign (12 Nov 2026)

| Check | Result |
|---|---|
| Navigation | Experience, Projects, Architecture, Resume (when `site/src/resume.json` exists), Ask |
| Hero | Name, role, two-sentence intro, availability; View Projects, View Resume (when available), Start Portfolio Tour; no Download Resume, no LinkedIn |
| Outcomes | 10+ applications to AKS, days → hours lead time, ~45% fewer false-positive alerts; all three checked against the MITIE (Teknip Technology) role in `content.json` and labelled as professional experience |
| Architecture overview | Delivery, infrastructure and reliability SVGs from `site/diagrams.py`; relationships checked against `pipelines/`, `scripts/deploy_with_rollback.sh`, `envs/lab/main.tf` (NSGs per spoke, private-endpoint NSG, DNS links to hub/app/data, storage public access off) and the SLO rules/postmortem; tabs with keyboard support and deep links (`#arch-delivery` etc.) |
| Case studies | All six use the same sections; scope table marks each part as Ran locally, Simulation, Checked in CI or Not yet run on Azure; no Azure deployment results are claimed |
| Walkthroughs | Scene-based pages are labelled Interactive walkthrough; MP4 recordings (all six exist) are labelled Recorded demo |
| Voice | Speech failure investigated in Chrome 157 on Windows (3 local Microsoft voices, 3 network Google voices, no Telugu voice): default, local, network voices and cancel-then-speak all played after a click. Hardened anyway in `speech.js`: local voices preferred, sentence-by-sentence speech (avoids Chrome's ~15 s cut-off on network voices), wait for voices, keep utterances referenced, retry once on failure, watchdog for silent failure, cancel on `pagehide`, friendly messages with no error codes |
| Tour | Next/Back/Stop/Mute, captions, highlights and switches the matching diagram, no overlapping narration, Escape stops, works muted and without speech support; welcome attempted once per tab session; microphone never created |
| Tests | Node 22/22, browser 32/32 (Chrome, Playwright, speech stand-ins for blocked, failing, silent and missing speech) |

Not verifiable here: real speaker output, Safari/Firefox autoplay behaviour, and the resume page (waiting for the approved resume).

## Resume, narration and mobile diagrams (12 Nov 2026)

| Check | Result |
|---|---|
| Resume files | Approved `.docx` had no GitHub, repository or project links; one clickable Portfolio line added to the contact band. Text diff against the original: only that line. DOCX validated; PDF renders on 3 pages like the original; both contain exactly one external link (the portfolio URL) |
| View Resume | Hero button and Resume nav item open `resume.html`, which shows the PDF (desktop) or page images (phones / no PDF viewer). No download button. Screen-reader text matches the approved resume |
| Contact data | The site's own pages and the assistant show the email from the resume; the phone number appears only inside the published resume PDF |
| Narration | Reproduced Delivery → Infrastructure in Chrome 157 / Windows 4 times: each step change cancelled the previous utterance and the new one started (local voice). Most likely cause of the reported "Audio couldn't start": the 3.5 s start watchdog firing while Windows' speech engine was still starting, and it cancelled speech Chrome already reported as playing. Fixed: speech reported as playing counts as started, 6 s start window, 200 ms settle + resume after cancel, one retry. Narration now starts only from Play narration |
| Prerecorded narration | Not possible here: no speech engine in the build environment and the recorded demos have no voice track |
| Phone diagrams | Vertical layouts for delivery, infrastructure and reliability at ≤ 640 px, rendered at ≥ 0.85 scale, no sideways scroll |
| Tests | Node 23/23, browser 34/34 |

## Recruiter layout, Azure palette and audio controls (12 Nov 2026)

| Check | Result |
|---|---|
| Hero | View Projects + View Resume (primary); Play intro + Start Portfolio Tour + Intro transcript (secondary); employer outcomes card labelled as professional experience |
| Featured projects | Directly after the hero; AKS Delivery and SRE Incident Lab cards show problem, what I built, verified result with Local/Simulated label, case study / recorded demo / interactive walkthrough links; other four labs listed with labels. No lab is labelled Azure-validated |
| Delivery diagram | Rebuilt from `pipelines/azure-pipelines.yml`, `docs/approvals.md` (dev: none, qa: branch control, prod: approval + branch control) and `scripts/deploy_with_rollback.sh`: three stages each with helm upgrade and an explicit smoke test, approval gate inside Prod, pass/fail arrows, one rollback lane. Phone layout shows the same steps vertically. Delivery tab selected on load |
| Audio | Nothing plays on load or on a first click elsewhere; intro plays only from Play intro, with transcript, Pause/Resume and Stop; tour narration Play/Pause/Resume, cancelled on step change; intro and tour never overlap; friendly fallbacks |
| Paths | Full browser suite run with the site served under `/my-profile/` (as on GitHub Pages) and at the root: 39/39 both |
| Tests | Node 23/23, browser 40/40 |
| Live audio fix | Live Chrome 157 / Windows: after speechSynthesis.pause() the engine finished the sentence, then the next sentence hung after resume() (speaking=true, no start/end for 9 s). Pause now cancels at the current sentence and Resume repeats that sentence; the engine's pause()/resume() is no longer used (test added) |

## Publishing
The repository is committed locally. Pushing to GitHub, enabling Pages and checking the live URLs need GitHub access. The final resume links are added only after the live site responds.

## Listen to Portfolio and latest role (13 Nov 2026)

| Check | Result |
|---|---|
| Hero | View Projects, View Resume and one *Listen to Portfolio* button; Play intro, Start Portfolio Tour, Intro transcript, the intro panel and the tour bar are removed (`tour.js` deleted). Project pages keep their recorded demos and interactive walkthroughs |
| Narration | `profile.narration`, 164 words (about 50–60 s at a normal rate), English. Opens with the full name, Azure DevOps and SRE focus and 11+ years; latest role at Pulse Data Labs (URUS, Feb–Sep 2026); delivery lab rollback described as a local run, SRE lab incident as simulated; ends with View Projects and View Resume. Every fact checked against `content.json` and `resume.json` |
| Playback | Starts only on click; button becomes Stop Audio and returns on stop, completion or error; replays from the start; seven rapid clicks never queue overlapping speech; Escape stops; cancelled on `pagehide`; no microphone, SpeechRecognition or scrolling |
| Fallback | No speech support, a failing voice, blocked audio and silent speech all show a short message and the narration text, with no extra audio button. In headless Chrome (no voices installed) the real fallback appeared |
| Speech fix | The sentence splitter broke "1.1.0" into fragments; it now splits only at punctuation followed by a space |
| Experience | Hero card: Senior DevOps Engineer · Pulse Data Labs · Client: URUS · Feb 2026 – Sep 2026, then Teknip Technology Pvt Ltd (MITIE, May 2024 – Feb 2026) with the 10+ AKS apps, days → hours and ~45% results. Timeline, resume text and narration checked for the same names, dates and attribution |
| Mobile | Hero buttons fit at 320, 375, 414 and 768 px with no horizontal scroll |
| Tests | Node 23/23; browser 32/32 with the site served under `/my-profile/` |

Not verifiable here: real speaker output and exact spoken length (the test browser has no voices).

