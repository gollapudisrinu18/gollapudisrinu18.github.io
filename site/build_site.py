#!/usr/bin/env python3
"""Build the portfolio website into _site/ (GitHub Pages artifact).

  python site/build_site.py                     # build with committed diagrams
  python site/build_site.py --render-diagrams   # re-render Mermaid -> SVG (needs mmdc)

Inputs:
  site/config.json           GitHub user, repo, branch, Pages base URL
  site/src/content.json      profile, experience, skills, project metadata
  site/src/kb-extra.json     assistant fallback text and Telugu answers
  projects/*/docs/architecture.md   Mermaid diagrams
  projects/*/docs/demo-output.txt   real demo output (tools/capture_demos.py)
Outputs:
  _site/                      the website
  projects/*/docs/demo.md     demo recording script and captions
"""
import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys

from jinja2 import Environment, FileSystemLoader, select_autoescape

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "_site")
STATIC = os.path.join(HERE, "static")
DIAGRAMS = os.path.join(STATIC, "assets", "diagrams")
VIDEOS = os.path.join(STATIC, "assets", "video")

MERMAID = re.compile(r"```mermaid\n(.*?)```", re.S)


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def render_mermaid(src, out_svg):
    cfg = os.path.join(HERE, "puppeteer.json")
    mmd = out_svg[:-4] + ".mmd"
    with open(mmd, "w") as fh:
        fh.write(src)
    subprocess.run(["mmdc", "-p", cfg, "-i", mmd, "-o", out_svg, "-b", "white",
                    "-c", os.path.join(HERE, "mermaid.json")], check=True, capture_output=True)
    os.remove(mmd)


def diagrams_for(project, render):
    """Return [{file, title, source}] for the project's architecture diagrams."""
    text = open(os.path.join(ROOT, "projects", project["dir"], "docs", "architecture.md"), encoding="utf-8").read()
    titles = re.findall(r"^## (.+)$", text, re.M)
    out = []
    for n, src in enumerate(MERMAID.findall(text), start=1):
        name = f"{project['slug']}-{n}.svg"
        path = os.path.join(DIAGRAMS, name)
        digest = hashlib.sha256(src.encode()).hexdigest()[:12]
        stamp = path + ".sha"
        current = open(stamp).read() if os.path.exists(stamp) else ""
        if render and (not os.path.exists(path) or current != digest):
            os.makedirs(DIAGRAMS, exist_ok=True)
            render_mermaid(src, path)
            with open(stamp, "w") as fh:
                fh.write(digest)
        if not os.path.exists(path):
            sys.exit(f"missing diagram {name}; run with --render-diagrams")
        title = titles[n - 1] if n - 1 < len(titles) else "Architecture"
        out.append({"file": name, "title": title, "source": src.strip()})
    return out


def demo_sections(project):
    path = os.path.join(ROOT, "projects", project["dir"], "docs", "demo-output.txt")
    text = open(path, encoding="utf-8").read()
    cmd, _, rest = text.partition("\n")
    parts = re.split(r"^=== (.+?) ===$", rest, flags=re.M)
    sections = []
    for k in range(1, len(parts), 2):
        sections.append({"title": parts[k].strip(), "body": parts[k + 1].strip("\n")})
    return cmd, sections, text


def colorize(text):
    out = []
    for line in html.escape(text).splitlines():
        if re.search(r"\b(PASS|ADMITTED|MET|VERIFIED|processed)\b", line) and "FAIL" not in line:
            line = f'<span class="pass">{line}</span>'
        elif re.search(r"\b(FAIL|FAILED|REJECTED|BREACH|MISSED|poison)\b", line):
            line = f'<span class="fail">{line}</span>'
        elif line.startswith("$ ") or line.startswith("==="):
            line = f'<span class="head">{line}</span>'
        out.append(line)
    return "\n".join(out)


def links_for(cfg, project):
    gh = f"https://github.com/{cfg['github_user']}/{cfg['repo']}"
    tree = f"{gh}/tree/{cfg['branch']}/projects/{project['dir']}"
    blob = f"{gh}/blob/{cfg['branch']}/projects/{project['dir']}"
    query = f'is:issue "[{project["title_short"]}]"'
    return {
        "source": tree,
        "architecture": f"{blob}/docs/architecture.md",
        "issues_doc": f"{blob}/docs/issues.md",
        "postmortem": f"{blob}/docs/postmortem.md" if os.path.exists(
            os.path.join(ROOT, "projects", project["dir"], "docs", "postmortem.md")) else None,
        "issues": f"{gh}/issues?q=" + query.replace(" ", "+").replace('"', "%22"),
        "readme": f"{blob}/README.md",
        "demo_page": f"demos/{project['slug']}.html",
        "case": f"projects/{project['slug']}.html",
    }


def contact_entry(contact):
    links = []
    if contact.get("resume_pdf"):
        links.append({"label": "Download resume (PDF)", "href": contact["resume_pdf"]})
    if contact.get("linkedin_url"):
        links.append({"label": "LinkedIn", "href": contact["linkedin_url"]})
    if contact.get("email"):
        links.append({"label": "Email", "href": "mailto:" + contact["email"]})
    if links:
        answer = "You can reach him through the links below. He is an immediate joiner and is looking for fully remote roles."
    else:
        answer = ("Contact details are kept off this public site. Please use the contact information on his resume, "
                  "or open an issue on the GitHub repository.")
    links.append({"label": "GitHub repository", "href": "{repo_url}"})
    return {"id": "contact", "kind": "meta", "title": "How to contact",
            "keywords": ["contact", "email", "phone", "reach", "linkedin", "call him", "resume", "cv"],
            "answer": answer, "links": links}


def check_contact(cfg):
    """Return only the contact links that are real; warn about the rest so nothing broken ships."""
    c = dict(cfg.get("contact") or {})
    out = {}
    pdf = (c.get("resume_pdf") or "").strip().lstrip("/")
    if pdf:
        if pdf.lower().endswith(".pdf") and os.path.isfile(os.path.join(STATIC, pdf)):
            out["resume_pdf"] = pdf
        else:
            print(f"WARNING: resume_pdf '{pdf}' is not a PDF under site/static; the resume button is hidden")
    li = (c.get("linkedin_url") or "").strip()
    if li:
        if re.match(r"^https://([a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9_-]+/?$", li):
            out["linkedin_url"] = li
        else:
            print(f"WARNING: linkedin_url '{li}' is not a linkedin.com/in/ profile URL; the LinkedIn link is hidden")
    em = (c.get("email") or "").strip()
    if em:
        if re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", em, re.I):
            out["email"] = em
        else:
            print(f"WARNING: email '{em}' is not valid; the Email link is hidden")
    missing = [k for k in ("resume_pdf", "linkedin_url", "email") if k not in out]
    if missing:
        print("Contact links not configured (hidden on the site): " + ", ".join(missing))
    return out


def build_kb(content, extra, projects, contact=None):
    contact = contact or {}
    p = content["profile"]
    te = extra["te"]
    entries = [
        {"id": "about", "kind": "career", "title": "About Srinivasa Rao Gollapudi",
         "keywords": ["tell me about", "who is", "srinivasa", "about him", "introduce", "background", "summary", "profile"],
         "keywords_te": ["గురించి", "ఎవరు", "శ్రీనివాస", "పరిచయం"],
         "answer": p["summary"], "answer_te": te["about"],
         "links": [{"label": "Experience", "href": "index.html#experience"}, {"label": "Projects", "href": "index.html#projects"}]},
        {"id": "azure-devops", "kind": "career", "title": "Azure DevOps experience",
         "keywords": ["azure devops", "pipelines", "ci/cd", "cicd", "yaml", "release", "devops experience", "build and release",
                      "in production", "production work", "devops work"],
         "keywords_te": ["డెవాప్స్", "డెవ్‌ఆప్స్", "పైప్‌లైన్", "అనుభవం"],
         "answer": ("Work experience: at MITIE (Teknip Technology) he created multi-stage Azure DevOps YAML pipelines with environment "
                    "approvals, ACR image scanning and Helm deployments to AKS for 10+ applications, cutting release lead "
                    "time from days to hours. At LSEG (Tech Mahindra, Technical Lead) he owned the Azure DevOps CI/CD "
                    "platform for 20+ application modules on reusable YAML templates, cutting deployment effort by 50%+. "
                    "At URUS (Pulse Data Labs) he managed AKS workloads deployed through Azure DevOps and GitHub Actions."),
         "answer_te": te["azure-devops"],
         "links": [{"label": "Experience timeline", "href": "index.html#experience"}],
         "lab_note": {"text": ("Portfolio lab (synthetic, built to verify the pattern): the AKS Delivery Platform lab promotes one "
                               "image Dev → QA → Prod with an approval gate. In its demo, release 1.1.0 fails the smoke test and "
                               "the pipeline restores 1.0.0."),
                      "text_te": te["lab-aks"],
                      "links": [{"label": "AKS delivery case study", "href": "projects/aks-delivery-platform.html"},
                                {"label": "Watch the rollback demo", "href": "demos/aks-delivery-platform.html"}]}},
        {"id": "sre", "kind": "career", "title": "SRE and reliability experience",
         "keywords": ["sre", "site reliability", "reliability", "on-call", "on call", "slo", "error budget", "postmortem", "incident response"],
         "keywords_te": ["ఎస్ఆర్ఈ", "రిలయబిలిటీ"],
         "answer": ("Work experience: at Pulse Data Labs he served as L3 escalation in a 24x7 PagerDuty on-call rotation, troubleshooting "
                    "Kubernetes failures such as CrashLoopBackOff, OOMKilled pods, ingress and DNS issues. He defined SLIs, "
                    "SLOs and error budgets with application teams, wrote blameless postmortems and prepared disaster "
                    "recovery plans against RTO and RPO targets. At MITIE he tuned alerting and reduced false-positive alerts by about 45%."),
         "answer_te": te["sre"],
         "links": [{"label": "Experience timeline", "href": "index.html#experience"}],
         "lab_note": {"text": ("Portfolio lab (simulated incident): the AKS Observability and SRE lab walks from a 14.4x "
                               "burn-rate page to a trace-led investigation, a cache-fallback mitigation and a blameless postmortem."),
                      "text_te": te["lab-sre"],
                      "links": [{"label": "SRE lab case study", "href": "projects/aks-observability-sre-lab.html"},
                                {"label": "Watch the incident demo", "href": "demos/aks-observability-sre-lab.html"}]}},
        {"id": "experience", "kind": "career", "title": "Work history and employers",
         "keywords": ["experience", "work history", "employers", "companies", "worked", "career", "jobs", "years", "clients"],
         "keywords_te": ["కంపెనీలు", "ఉద్యోగాలు", "కెరీర్"],
         "answer": "11+ years in IT. " + " ".join(
             f"{e['title']} at {e['company']} (client {e['client']}), {e['dates']}." for e in content["experience"]),
         "links": [{"label": "Experience timeline", "href": "index.html#experience"}]},
        {"id": "skills", "kind": "career", "title": "Technical skills",
         "keywords": ["skills", "tools", "technologies", "tech stack", "terraform", "kubernetes", "aks", "stack"],
         "keywords_te": ["నైపుణ్యాలు", "టెర్రాఫార్మ్", "కుబెర్నెటిస్"],
         "answer": " ".join(f"{s['group']}: {', '.join(s['items'])}." for s in content["skills"]),
         "links": [{"label": "Skills", "href": "index.html#skills"}]},
        {"id": "availability", "kind": "career", "title": "Availability and remote work",
         "keywords": ["available", "availability", "remote", "notice period", "join", "joining", "relocate", "hire", "start"],
         "keywords_te": ["రిమోట్", "జాయిన్", "అందుబాటు"],
         "answer": "He is an immediate joiner and is looking for fully remote roles only. He is based in Bangalore, India.",
         "answer_te": te["availability"], "links": []},
        {"id": "education", "kind": "career", "title": "Education",
         "keywords": ["education", "degree", "mba", "university", "qualification", "study"],
         "keywords_te": ["చదువు", "విద్య"],
         "answer": content["education"] + ".", "links": []},
        {"id": "certifications", "kind": "meta", "title": "Certifications",
         "keywords": ["certification", "certified", "certificate", "az-104", "az-400", "cka"],
         "answer": "No certifications are listed in his resume, so I can't confirm any. The projects in this portfolio show the hands-on work instead.",
         "links": []},
        contact_entry(contact),
        {"id": "synthetic", "kind": "meta", "title": "Are the projects real client work?",
         "keywords": ["real", "client code", "synthetic", "employer", "fake", "simulated", "production data", "is this real"],
         "answer": ("No. The six projects are original portfolio labs inspired by his experience. They use synthetic apps, "
                    "data, logs and incidents and contain no employer code or client details. Career facts come from his resume; "
                    "lab results come from running the labs."),
         "links": [{"label": "All projects", "href": "index.html#projects"}]},
        {"id": "projects", "kind": "meta", "title": "Projects in the portfolio",
         "keywords": ["projects", "portfolio", "labs", "what did he build", "case studies", "github"],
         "keywords_te": ["ప్రాజెక్టులు", "ప్రాజెక్ట్స్"],
         "answer": "Six Azure labs: " + "; ".join(f"{pr['title']} ({pr['tier']})" for pr in projects) + ".",
         "answer_te": te["projects"],
         "links": [{"label": pr["title_short"], "href": f"projects/{pr['slug']}.html"} for pr in projects[:4]]},
    ]
    special = {
        "aks-delivery-platform": {
            "how": ("how does the aks rollback work", "rollback", "roll back", "smoke test", "helm rollback", "bad release", "rollback work"),
            "how_te": ["రోల్‌బ్యాక్", "రోల్ బ్యాక్"],
            "answer": ("Lab result: each deployment records the current Helm revision, runs helm upgrade --wait, then a smoke test "
                       "that checks /healthz, /version and two orders API calls. If the smoke test fails, the script runs helm "
                       "rollback to the recorded revision, smoke-tests the restored version and still fails the stage so later "
                       "environments are not touched. In the demo, 1.1.0 failed with HTTP 500 and 1.0.0 was restored as revision 3."),
            "answer_te": te["rollback"],
        },
        "aks-observability-sre-lab": {
            "how": ("sre incident", "incident demo", "latency incident", "burn rate", "postmortem demo", "incident"),
            "how_te": ["ఇన్సిడెంట్", "సంఘటన"],
            "answer": ("Simulated incident: an inventory dependency slowed to about 800 ms, so 58% of checkouts missed the 300 ms SLO "
                       "while still returning 200. The 14.4x burn-rate alert paged 16 minutes in, span timings pointed to "
                       "inventory.lookup, and the cache fallback mitigated it at 27 minutes. It used 3.6% of the monthly error "
                       "budget, and the postmortem lists four action items."),
            "answer_te": te["incident-demo"],
            "kind": "incident",
        },
    }
    for pr in projects:
        base_kw = [pr["title_short"].lower()] + [s.lower() for s in pr["keywords"]]
        entries.append({
            "id": f"project-{pr['slug']}", "kind": "lab", "title": pr["title"],
            "keywords": base_kw,
            "answer": f"{pr['short']} Result: {pr['result']}",
            "links": [{"label": "Case study", "href": f"projects/{pr['slug']}.html"},
                      {"label": "Demo", "href": f"demos/{pr['slug']}.html"},
                      {"label": "Source", "href": pr["links"]["source"]}],
        })
        entries.append({
            "id": f"demo-{pr['slug']}", "kind": special.get(pr["slug"], {}).get("kind", "lab"), "intent": "demo",
            "title": f"{pr['title_short']} demo",
            "keywords": [f"{k} demo" for k in base_kw[:2]] + [f"demo {base_kw[0]}"],
            "answer": f"Demo: {pr['demo']['intro']} The walkthrough shows the architecture, the real run output and the verified result.",
            "links": [{"label": "Play the demo", "href": f"demos/{pr['slug']}.html"},
                      {"label": "Case study", "href": f"projects/{pr['slug']}.html"}],
        })
        if pr["slug"] in special:
            sp = special[pr["slug"]]
            entries.append({
                "id": f"how-{pr['slug']}", "kind": sp.get("kind", "lab"), "title": pr["title"] + " details",
                "keywords": list(sp["how"]), "keywords_te": sp["how_te"],
                "answer": sp["answer"], "answer_te": sp["answer_te"],
                "links": [{"label": "Play the demo", "href": f"demos/{pr['slug']}.html"},
                          {"label": "Case study", "href": f"projects/{pr['slug']}.html"}],
            })
    # "Show me the SRE incident demo" should land on the incident demo
    for e in entries:
        if e["id"] == "demo-aks-observability-sre-lab":
            e["keywords"] += ["sre incident demo", "incident demo", "sre demo"]
            e["keywords_te"] = ["డెమో"]
            e["answer"] = ("Simulated incident demo: steady traffic, then a slow inventory dependency pushes the burn rate past "
                           "the 14.4x paging threshold. Span timings point to inventory.lookup, the cache fallback is enabled, "
                           "and the burn rate returns to 0x. The full timeline and postmortem are on the case study page.")
            e["answer_te"] = te["incident-demo"]
    return {"version": 1, "unavailable": extra["unavailable"], "unavailable_te": extra["unavailable_te"],
            "samples": extra["samples"], "entries": entries}


DEMO_MD = """# Demo: {title}

**Format:** {format_line}

- Browser walkthrough (captioned, keyboard accessible): {walk_url}
{video_line}- Run it yourself: `{run}` from `projects/{dir}`

## Recording script

| Scene | Show on screen | Caption |
|---|---|---|
{rows}

## Captured output

The walkthrough uses this output, captured from a real run by `tools/capture_demos.py`:

```text
{output}
```
"""


def write_demo_md(cfg, pr, sections, raw, has_video):
    site = cfg["pages_url"].rstrip("/")
    rows = [f"| 1 | Title card | {pr['demo']['intro']} |"]
    n = 2
    for d in pr["diagrams"]:
        rows.append(f"| {n} | Diagram: {d['title']} | {d['title']} |")
        n += 1
    for sec, cap in zip(sections, pr["demo"]["captions"]):
        rows.append(f"| {n} | Terminal: {sec['title']} | {cap} |")
        n += 1
    rows.append(f"| {n} | Result card | {pr['result']} |")
    fmt = ("Captioned MP4 screen recording of the browser walkthrough, plus the walkthrough itself"
           if has_video else "Captioned browser walkthrough (recording script below)")
    video_line = (f"- Video (MP4, captions in WebVTT): {site}/assets/video/{pr['slug']}.mp4\n" if has_video else "")
    text = DEMO_MD.format(title=pr["title"], format_line=fmt, walk_url=f"{site}/demos/{pr['slug']}.html",
                          video_line=video_line, run=pr["run"], dir=pr["dir"], rows="\n".join(rows),
                          output=raw.strip())
    with open(os.path.join(ROOT, "projects", pr["dir"], "docs", "demo.md"), "w", encoding="utf-8") as fh:
        fh.write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render-diagrams", action="store_true")
    args = ap.parse_args()

    cfg = load(os.path.join(HERE, "config.json"))
    content = load(os.path.join(HERE, "src", "content.json"))
    extra = load(os.path.join(HERE, "src", "kb-extra.json"))
    cfg["repo_url"] = f"https://github.com/{cfg['github_user']}/{cfg['repo']}"

    projects = content["projects"]
    for pr in projects:
        pr["title_short"] = pr["title"].split(" with ")[0]
        pr["keywords"] = pr.get("keywords") or [s for s in pr["stack"]]
        pr["links"] = links_for(cfg, pr)
        pr["diagrams"] = diagrams_for(pr, args.render_diagrams)
        cmd, sections, raw = demo_sections(pr)
        pr["demo_cmd"], pr["sections"] = cmd, sections
        if len(sections) != len(pr["demo"]["captions"]):
            sys.exit(f"{pr['slug']}: {len(sections)} demo sections but {len(pr['demo']['captions'])} captions")
        for sec, cap in zip(sections, pr["demo"]["captions"]):
            sec["caption"] = cap
            sec["html"] = colorize(sec["body"])
        pr["video"] = os.path.exists(os.path.join(VIDEOS, pr["slug"] + ".mp4"))
        pr["vtt"] = os.path.exists(os.path.join(VIDEOS, pr["slug"] + ".vtt"))
        write_demo_md(cfg, pr, sections, raw, pr["video"])

    cfg["contact"] = check_contact(cfg)
    kb = build_kb(content, extra, projects, cfg["contact"])
    kb_json = json.dumps(kb, ensure_ascii=False, indent=1).replace("{repo_url}", cfg["repo_url"])

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(STATIC, OUT, ignore=shutil.ignore_patterns("*.sha"))
    os.makedirs(os.path.join(OUT, "data"), exist_ok=True)
    with open(os.path.join(OUT, "data", "knowledge.json"), "w", encoding="utf-8") as fh:
        fh.write(kb_json)

    env = Environment(loader=FileSystemLoader(os.path.join(HERE, "templates")),
                      autoescape=select_autoescape(["html"]))
    common = {"cfg": cfg, "profile": content["profile"], "projects": projects, "samples": extra["samples"],
              "welcome": extra["welcome"]}

    def write(rel, template, **ctx):
        path = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        depth = rel.count("/")
        html_text = env.get_template(template).render(root="../" * depth or "./", page=rel, **common, **ctx)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html_text)

    lead = [p for p in projects if p.get("lead")]
    write("index.html", "index.html", content=content, lead=lead,
          flagship=[p for p in projects if p["tier"] == "flagship" and p not in lead],
          supporting=[p for p in projects if p["tier"] == "supporting" and p not in lead])
    for pr in projects:
        write(f"projects/{pr['slug']}.html", "project.html", p=pr)
        write(f"demos/{pr['slug']}.html", "demo.html", p=pr)
    write("404.html", "404.html")
    with open(os.path.join(OUT, ".nojekyll"), "w") as fh:
        fh.write("")
    pages = sum(len(files) for _, _, files in os.walk(OUT) if True)
    print(f"Built {OUT} ({pages} files, {len(kb['entries'])} knowledge entries)")


if __name__ == "__main__":
    main()
