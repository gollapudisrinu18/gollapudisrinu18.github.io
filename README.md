# Srinivasa Rao Gollapudi · Azure DevOps & SRE Portfolio

**Senior Azure DevOps Engineer | Site Reliability Engineer (SRE)** · 11+ years in IT · Immediate joiner · Remote only · Bangalore, India

**Portfolio:** https://gollapudisrinu18.github.io/my-profile/

That one link covers everything: professional experience, skills, the architecture overview, six case studies with diagrams, recorded demos and interactive walkthroughs, a guided portfolio tour, and the *Ask My Portfolio* assistant. This repository holds the source code for the six labs and the website.

> The labs are original portfolio projects inspired by my work. They use synthetic applications, data, logs and incidents. No employer code, client internals or credentials are included. Each case study states what ran locally, what is simulated, what is checked in CI and what has not yet been run on Azure.

## Professional experience highlights

From my role as DevOps Engineer at Teknip Technology (client: MITIE), May 2024 – Feb 2026:

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

- **Navigation:** Experience, Projects, Architecture, Resume and Ask.
- **Featured projects:** directly below the hero, the AKS Delivery Platform and AKS Observability and SRE Incident Lab cards show the problem, what was built, one verified result labelled Local / Simulated / Azure-validated, and links to the case study, recorded demo and interactive walkthrough. The other four labs follow in a compact list.
- **Architecture overview:** three diagrams drawn from the project source: delivery (Azure Pipelines → ACR → Dev/QA/Prod on AKS with an approval gate, smoke tests and rollback), infrastructure (Terraform hub-and-spoke, NSGs, private endpoint, private DNS) and reliability (metrics and traces → SLO burn-rate alert → investigation → mitigation → postmortem). They are generated as inline SVG by `site/diagrams.py`.
- **Audio intro and portfolio tour:** audio plays only after a click. *Play intro* (next to the hero) reads a short welcome with a transcript and Play / Pause / Resume / Stop controls. *Start Portfolio Tour* walks through the three diagrams with captions, Next, Back, Mute, Stop and optional narration (Play / Pause / Resume narration). Each step change cancels the previous narration, failures fall back to text with a "Try audio again" control, and neither ever uses the microphone.
- **Ask My Portfolio:** typed questions (voice input optional) answered from the resume and the case studies. Answers are labelled as work experience or portfolio lab, and link to the relevant diagram, case study, walkthrough or resume. English and Telugu.
- **Resume:** *View Resume* opens the approved resume as a PDF inside the portfolio (`resume.html`). Desktop browsers show it in their PDF viewer; phones and browsers without one see images of the same pages. There is no download button (browser PDF viewers have their own save controls). A text version from `site/src/resume.json` is available to screen readers.

## Run everything locally

Python 3.10+ is enough for all six local demos.

```bash
pip install flask pytest pyyaml cryptography opentelemetry-api jinja2
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
  src/resume.json                    resume text (from the approved .docx) for screen readers and the assistant
  static/assets/resume/              the resume PDF shown on the site and its page images
  templates/, static/                page templates, CSS, JavaScript (speech, tour, assistant), videos
tools/                               demo capture and recording, issue import, Mermaid check, configure
tests/site/                          assistant tests (Node) and browser tests (Playwright)
profile/README.md                    GitHub profile README
docs/VERIFICATION.md                 what was checked, and what still needs Azure
.github/workflows/                   CI and GitHub Pages deployment
```

## Update the resume

1. Put the approved resume PDF at `site/static/assets/resume/Srinivasa_Rao_Gollapudi_Resume.pdf`.
2. Regenerate the page images: `pdftoppm -png -r 150 <pdf> site/static/assets/resume/resume-page`, then convert to WebP (or keep PNG and update the names).
3. Update `site/src/resume.json` if the wording changed, then run `python site/build_site.py`.

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
