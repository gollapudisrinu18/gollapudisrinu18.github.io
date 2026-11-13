# Srinivasa Rao Gollapudi · Azure DevOps & SRE Portfolio

**Senior Azure DevOps Engineer | Site Reliability Engineer (SRE)** · 11+ years in IT · Immediate joiner · Remote only · Bangalore, India

**Portfolio:** https://gollapudisrinu18.github.io/my-profile/

That one link covers everything: professional experience, skills, the architecture overview, six case studies with diagrams, recorded demos and interactive walkthroughs, and a short spoken walkthrough (*Listen to Portfolio*). This repository holds the source code for the six labs and the website.

> The labs are original portfolio projects inspired by my work. They use synthetic applications, data, logs and incidents. No employer code, client internals or credentials are included. Each case study states what ran locally, what is simulated, what is checked in CI and what has not yet been run on Azure.

## Professional experience highlights

Latest role: Pulse Data Labs · Senior DevOps Engineer · Client: URUS · Feb 2026–Sep 2026 (AKS deployments, reusable Terraform modules, L3 on-call escalation).

From my role as DevOps Engineer at Teknip Technology Pvt Ltd (client: MITIE), May 2024–Feb 2026:

- 10+ applications deployed to AKS
- Release lead time reduced from days to hours
- ~45% fewer false-positive alerts

## Case studies

Start with the first two. Every case study follows the same format: problem, environment, architecture, implementation, engineering decisions, failure scenario, recovery, verified result, walkthrough, and scope and evidence.

| Case study | Failure scenario shown | Source |
|---|---|---|
| [AKS Delivery Platform with Azure DevOps](https://gollapudisrinu18.github.io/my-profile/projects/aks-delivery-platform.html) | Release 1.1.0 fails its smoke test; Helm rolls back to 1.0.0 | [01-aks-delivery-platform](projects/01-aks-delivery-platform) |
| [AKS Observability and SRE Incident Lab](https://gollapudisrinu18.github.io/my-profile/projects/aks-observability-sre-lab.html) | Dependency latency burns the SLO; trace-led diagnosis, mitigation, postmortem | [03-aks-observability-sre-lab](projects/03-aks-observability-sre-lab) |
| [Azure Hub-and-Spoke Infrastructure with Terraform](https://gollapudisrinu18.github.io/my-profile/projects/azure-hub-spoke-terraform.html) | Missing private DNS link sends traffic to the public endpoint (403) | [02-azure-hub-spoke-terraform](projects/02-azure-hub-spoke-terraform) |
| [Azure DevSecOps Software Supply Chain](https://gollapudisrinu18.github.io/my-profile/projects/azure-devsecops-supply-chain.html) | Unsigned, tag-only and tampered images rejected at admission | [04-azure-devsecops-supply-chain](projects/04-azure-devsecops-supply-chain) |
| [Azure Functions Event-Driven Processing](https://gollapudisrinu18.github.io/my-profile/projects/azure-functions-event-processing.html) | Duplicate delivery, transient retries and poison messages | [05-azure-functions-event-processing](projects/05-azure-functions-event-processing) |
| [Azure Disaster Recovery and Restore Drill](https://gollapudisrinu18.github.io/my-profile/projects/azure-dr-restore-drill.html) | Data deleted on purpose, restored and verified by checksum | [06-azure-dr-restore-drill](projects/06-azure-dr-restore-drill) |

Every project folder has a `README.md` (setup, expected results, Azure prerequisites, billable resources, troubleshooting, cleanup), `docs/architecture.md`, `docs/issues.md` and `docs/demo.md`.

## What the website includes

- **Navigation:** Experience, Projects, Architecture and Résumé. No outside GitHub links: everything is on the one site.
- **Hero:** *View Projects*, *View Résumé* and one *Listen to Portfolio* button. The *Latest Role* card shows Pulse Data Labs; the Teknip Technology (MITIE) results sit with that role in the experience timeline.
- **Featured lab screenshots:** real output from the two featured labs (the rollback in the AKS delivery lab, the burn-rate alert and span timings in the SRE lab), captured from the interactive walkthroughs, linked to their case studies and labelled LOCAL / SIMULATED.
- **Source pages:** `source/` on the site lets visitors browse every file of the six labs: Markdown rendered, code highlighted with line numbers, a file tree, and the MIT license notice. Built by `site/source_pages.py` from files tracked by git; the build refuses anything that looks like a secret.
- **Featured projects:** directly below the hero, the AKS Delivery Platform and AKS Observability and SRE Incident Lab cards show the problem, what was built, one verified result labelled Local / Simulated / Azure-validated, and links to the case study, recorded demo and interactive walkthrough. The other four labs follow in a compact list.
- **Architecture overview:** three diagrams drawn from the project source: delivery (Azure Pipelines → ACR → Dev/QA/Prod on AKS with an approval gate, smoke tests and rollback), infrastructure (Terraform hub-and-spoke, NSGs, private endpoint, private DNS) and reliability (metrics and traces → SLO burn-rate alert → investigation → mitigation → postmortem). They are generated as inline SVG by `site/diagrams.py`.
- **Listen to Portfolio:** a roughly one-minute spoken walkthrough for recruiters, read by the browser's own speech synthesis (`speechSynthesis`), so it works on GitHub Pages with no backend or API keys. It starts only when the button is pressed; the same button reads *Stop Audio* while playing and returns to *Listen to Portfolio* when stopped, finished or failed. Every start replays from the beginning and rapid clicks never overlap. If speech is unavailable or fails, a short message and the narration text are shown. No microphone, chat, autoplay or scrolling. The script is `profile.narration` in `site/src/content.json`; the code is `static/assets/js/listen.js` and `speech.js`.
- **Résumé:** *View Résumé* opens a readable HTML résumé (`resume.html`) built from `site/src/resume.json`. It is view-only: no PDF viewer, no download buttons, and no PDF or Word file is published. The phone number stays off the public site.

## Run everything locally

Python 3.10+ is enough for all six local demos.

```bash
pip install flask pytest pyyaml cryptography opentelemetry-api jinja2 markdown pygments
for p in projects/*/; do (cd "$p" && python -m pytest -q tests); done
python tools/capture_demos.py          # runs all six demos, saves their output
python site/build_site.py              # builds the website into _site/
python -m http.server 8000 --directory _site   # open http://localhost:8000
```

Site tests (also run in CI):

```bash
node --test tests/site/kb.test.js                       # assistant answers and links
pip install playwright
python -m http.server 8765 --directory _site &
SITE_URL=http://127.0.0.1:8765/ python -m pytest -q tests/site/test_browser.py   # browser tests in Chrome
```

CI (`.github/workflows/ci.yml`) also runs `terraform validate` and `terraform test`, `helm lint`, and `promtool test rules`. Pushing to `main` deploys the site with `.github/workflows/pages.yml`.

## Repository layout

```
projects/
  01-aks-delivery-platform/          app, Helm chart, Azure Pipelines templates, rollback demo
  02-azure-hub-spoke-terraform/      Terraform modules, lab env, tests, DNS tools
  03-aks-observability-sre-lab/      instrumented service, Prometheus rules, Grafana, incident sim, postmortem
  04-azure-devsecops-supply-chain/   pipeline, Kyverno policies, admission webhook, Workload ID
  05-azure-functions-event-processing/  Function app, processor, local queue runtime
  06-azure-dr-restore-drill/         backup/restore library, drill, Azure PITR script, runbook
site/
  build_site.py                      website generator
  diagrams.py                        architecture overview diagrams (SVG)
  src/content.json                   profile, experience, skills and case study content
  src/kb-extra.json                  assistant samples, welcome text and Telugu answers
  src/resume.json                    résumé text (from the approved .docx), rendered as resume.html
  source_pages.py                    browsable source pages for the labs (source/ on the site)
  templates/, static/                page templates, CSS, JavaScript (speech, Listen to Portfolio), videos
tools/                               demo capture and recording, issue import, Mermaid check, configure
tests/site/                          assistant tests (Node) and browser tests (Playwright)
profile/README.md                    GitHub profile README
docs/VERIFICATION.md                 what was checked, and what still needs Azure
.github/workflows/                   CI and GitHub Pages deployment
```

## Update the résumé

1. Edit `site/src/resume.json` to match the approved Word résumé.
2. Run `python site/build_site.py`. The public page is HTML only; keep the Word file out of this repository.

## Import the issue backlogs

```bash
gh auth login
for f in projects/*/docs/issues.md; do python tools/import_issues.py "$f" --repo gollapudisrinu18/my-profile; done
```

## Use a different account or repository

```bash
python tools/configure.py --user <github-user> --repo <repo>
python site/build_site.py
```
