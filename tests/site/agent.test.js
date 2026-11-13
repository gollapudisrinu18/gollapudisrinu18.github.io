// node --test tests/site/agent.test.js   (run after `python site/build_site.py`)
const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");
const fs = require("node:fs");
const Core = require("../../site/static/assets/js/agent-core.js");
const read = (f) => JSON.parse(fs.readFileSync(path.join(__dirname, "../../_site/data", f), "utf8"));
const data = read("agent.json");
const kb = read("knowledge.json");
const fresh = () => Core.create(data, kb);
const PREF = "Open to remote-only Senior Azure DevOps Engineer and Site Reliability Engineer (SRE) roles.";

test("grounding data lists Pulse Data Labs first, as on the resume", () => {
  assert.strictEqual(data.roles[0].company, "Pulse Data Labs");
  assert.strictEqual(data.roles[0].client, "URUS");
  assert.strictEqual(data.roles[0].dates, "Feb 2026 – Sep 2026");
  assert.strictEqual(data.roles[1].company, "Teknip Technology Pvt Ltd");
  assert.strictEqual(data.profile.remote_pref, PREF);
  assert.strictEqual(data.projects.length, 6);
});

test("previous employer is Pulse Data Labs and follow-ups stay on that role", () => {
  const e = fresh();
  const a = e.ask("Who was his previous employer?");
  assert.strictEqual(a.kind, "career");
  assert.match(a.text, /most recent employer is Pulse Data Labs/);
  assert.match(a.text, /client URUS/);
  const b = e.ask("What were the results there?");
  assert.match(b.text, /no measured figures for this role/);
  assert.doesNotMatch(b.text, /10\+ applications|45%|days to hours/, "MITIE metrics must not be attributed to Pulse Data Labs");
  const c = e.ask("What tools did he use there?");
  assert.match(c.text, /PagerDuty, Backstage/);
});

test("MITIE metrics stay with Teknip Technology", () => {
  const e = fresh();
  const r = e.ask("What did he achieve at Teknip?");
  assert.match(r.title, /Teknip Technology Pvt Ltd \(client MITIE\)/);
  assert.match(r.text, /10\+ applications/);
});

test("remote-only preference is stated the same way everywhere", () => {
  for (const q of ["Is he open to remote roles?", "Would he relocate for an onsite job?", "How can I contact him?"]) {
    assert.ok(fresh().ask(q).text.includes(PREF), q);
  }
  assert.match(fresh().ask("Would he relocate for an onsite job?").text, /remote-only roles/);
});

test("explain this project covers problem, architecture, tools, implementation and outcome", () => {
  for (const p of data.projects) {
    const r = fresh().explain(p.slug);
    assert.strictEqual(r.kind, "guided");
    assert.strictEqual(r.label, "Guided tour · scripted from the case study");
    assert.deepStrictEqual(r.parts.map((x) => x.heading), ["Problem", "Architecture", "Tools", "Implementation", "Documented outcome"]);
    assert.match(r.note, /portfolio lab with synthetic data, not an employer result/);
    assert.match(r.spoken, /^Guided tour of /);
    assert.ok(r.links.some((l) => l.href === `projects/${p.slug}.html`));
  }
});

test("project follow-ups use the last project discussed", () => {
  const e = fresh();
  e.ask("Explain the AKS Delivery Platform project");
  const t = e.ask("What tools does it use?");
  assert.match(t.text, /Azure Pipelines, ACR, AKS, Helm/);
  const r = e.ask("How does it recover?");
  assert.match(r.text, /helm rollback/);
  const s = e.ask("Has it run on Azure?");
  assert.match(s.text, /Needs Azure \(not yet run\)/);
  const m = e.ask("tell me more");
  assert.strictEqual(m.project, "aks-delivery-platform");
});

test("missing information is reported, not invented", () => {
  for (const q of ["What is his salary expectation?", "Does he know Rust?"]) {
    const r = fresh().ask(q);
    assert.strictEqual(r.kind, "unavailable", q);
    assert.match(r.text, /don't (have|see)/, q);
  }
  assert.match(fresh().ask("Does he have certifications?").text, /No certifications are listed/);
});

test("which-project questions search the labs", () => {
  const r = fresh().ask("Which projects use Terraform?");
  assert.match(r.text, /Azure Hub-and-Spoke Infrastructure with Terraform/);
});
