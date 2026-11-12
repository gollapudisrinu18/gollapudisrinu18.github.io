# Srinivasa Rao Gollapudi · Azure DevOps & SRE Portfolio

**Senior Azure DevOps Engineer | Site Reliability Engineer (SRE)** · 11+ years in IT · Immediate joiner · Remote only

🌐 **Portfolio website:** https://gollapudisrinu18.github.io/my-profile/ (includes the *Ask My Portfolio* voice and text assistant)

This repository contains six hands-on Azure labs with source code, tests, architecture diagrams, recorded demos and issue backlogs, plus the website that presents them. Each project lives in its own folder and can be copied into a standalone repository.

> The labs are original portfolio projects inspired by my work. They use synthetic applications, data, logs and incidents. No employer code, client internals or credentials are included.

## Projects

| | Project | What it shows | Demo |
|---|---|---|---|
| ⭐ | [AKS Delivery Platform with Azure DevOps](projects/01-aks-delivery-platform) | Multi-stage Azure Pipelines, ACR, Helm on AKS, approvals, smoke test and automatic rollback | [Watch](https://gollapudisrinu18.github.io/my-profile/demos/aks-delivery-platform.html) |
| ⭐ | [Azure Hub-and-Spoke Infrastructure with Terraform](projects/02-azure-hub-spoke-terraform) | Reusable modules, peering, NSGs, private endpoints, private DNS, remote state, DNS incident fix | [Watch](https://gollapudisrinu18.github.io/my-profile/demos/azure-hub-spoke-terraform.html) |
| ⭐ | [AKS Observability and SRE Incident Lab](projects/03-aks-observability-sre-lab) | OpenTelemetry, Prometheus, Grafana, SLOs, burn-rate alerts, incident and postmortem | [Watch](https://gollapudisrinu18.github.io/my-profile/demos/aks-observability-sre-lab.html) |
| ⭐ | [Azure DevSecOps Software Supply Chain](projects/04-azure-devsecops-supply-chain) | Trivy, SBOM, Cosign with Key Vault, Kyverno admission, Entra Workload ID | [Watch](https://gollapudisrinu18.github.io/my-profile/demos/azure-devsecops-supply-chain.html) |
| | [Azure Functions Event-Driven Processing](projects/05-azure-functions-event-processing) | Queue trigger, idempotency, retries, poison messages, structured logs | [Watch](https://gollapudisrinu18.github.io/my-profile/demos/azure-functions-event-processing.html) |
| | [Azure Disaster Recovery and Restore Drill](projects/06-azure-dr-restore-drill) | Backup, restore, checksum verification, measured RTO and RPO | [Watch](https://gollapudisrinu18.github.io/my-profile/demos/azure-dr-restore-drill.html) |

Every project folder has a `README.md` (setup, expected results, Azure prerequisites, billable resources, troubleshooting, cleanup), `docs/architecture.md`, `docs/issues.md` and `docs/demo.md`.

## Run everything locally

Python 3.10+ is enough for all six local demos.

```bash
pip install flask pytest pyyaml cryptography opentelemetry-api jinja2
for p in projects/*/; do (cd "$p" && python -m pytest -q tests); done
python tools/capture_demos.py          # runs all six demos, saves their output
python site/build_site.py              # builds the website into _site/
python -m http.server 8000 --directory _site   # open http://localhost:8000
```

CI (`.github/workflows/ci.yml`) also runs `terraform validate` and `terraform test`, `helm lint`, `promtool test rules`, the assistant tests and browser tests in Chrome.

## Repository layout

```
projects/
  01-aks-delivery-platform/          app, Helm chart, Azure Pipelines templates, rollback demo
  02-azure-hub-spoke-terraform/      Terraform modules, lab env, tests, DNS tools
  03-aks-observability-sre-lab/      instrumented service, Prometheus rules, Grafana, incident sim, postmortem
  04-azure-devsecops-supply-chain/   pipeline, Kyverno policies, admission webhook, Workload ID
  05-azure-functions-event-processing/  Function app, processor, local queue runtime
  06-azure-dr-restore-drill/         backup/restore library, drill, Azure PITR script, runbook
site/                                website generator, templates, assets, assistant knowledge sources
tools/                               demo capture, demo recording, issue import, Mermaid check, configure
tests/site/                          assistant matching tests (Node) and browser tests (Playwright)
profile/README.md                    GitHub profile README
.github/workflows/                   CI and GitHub Pages deployment
```

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
