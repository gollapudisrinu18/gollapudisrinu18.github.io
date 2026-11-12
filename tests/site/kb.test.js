// node --test tests/site/kb.test.js   (run after `python site/build_site.py`)
const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");
const fs = require("node:fs");
const KB = require("../../site/static/assets/js/kb.js");
const data = JSON.parse(fs.readFileSync(path.join(__dirname, "../../_site/data/knowledge.json"), "utf8"));

const cases = [
  ["Tell me about Srinivasa", "about", "career"],
  ["What is your Azure DevOps experience?", "azure-devops", "career"],
  ["How does the AKS rollback work?", "how-aks-delivery-platform", "lab"],
  ["Show me the SRE incident demo", "demo-aks-observability-sre-lab", "incident"],
  ["Which projects are in the portfolio?", "projects", "meta"],
  ["Is he available for remote work?", "availability", "career"],
  ["Does he have SRE experience with on-call?", "sre", "career"],
  ["Tell me about the Terraform hub and spoke project", "project-azure-hub-spoke-terraform", "lab"],
  ["Show me the supply chain demo", "demo-azure-devsecops-supply-chain", "lab"],
  ["Does he have any certifications?", "certifications", "meta"],
  ["Is this real client code?", "synthetic", "meta"],
  ["What Azure DevOps work has Srinivasa done in production?", "azure-devops", "career"],
];

test("production question separates work experience from the lab", () => {
  const r = KB.answer(data, "What Azure DevOps work has Srinivasa done in production?", "en");
  assert.match(r.text, /^Work experience:/);
  assert.match(r.text, /10\+ applications/);
  assert.ok(r.labNote, "has a lab section");
  assert.match(r.labNote.text, /^Portfolio lab/);
  assert.deepStrictEqual(r.labNote.links.map(l => l.href),
    ["projects/aks-delivery-platform.html", "index.html#arch-delivery", "demos/aks-delivery-platform.html"]);
});

test("suggested questions cover experience, delivery, rollback, incident and availability", () => {
  assert.deepStrictEqual(data.samples.slice(0, 5), [
    "What Azure DevOps work has Srinivasa done in production?",
    "How is the delivery pipeline designed?",
    "How does the AKS rollback work?",
    "Show me the SRE incident demo",
    "Is he available for remote work?"]);
});

test("architecture and resume questions link to the right pages", () => {
  const d = KB.answer(data, "How is the delivery pipeline designed?", "en");
  assert.strictEqual(d.id, "delivery-architecture");
  assert.ok(d.links.some(l => l.href === "index.html#arch-delivery"));
  const r = KB.answer(data, "Can I view his resume?", "en");
  assert.strictEqual(r.id, "resume");
  const hasResume = fs.existsSync(path.join(__dirname, "../../_site/resume.html"));
  assert.strictEqual(r.links.some(l => l.href === "resume.html"), hasResume);
  assert.ok(!/use the contact information on his resume/i.test(JSON.stringify(data)), "no dead-end resume answers");
});

test("hub-and-spoke question finds the Terraform lab", () => {
  assert.strictEqual(KB.answer(data, "How is the hub and spoke network built?", "en").id, "project-azure-hub-spoke-terraform");
});
for (const [q, id, kind] of cases) {
  test(`matches: ${q}`, () => {
    const r = KB.answer(data, q, "en");
    assert.strictEqual(r.id, id, `got ${r.id} (score ${r.score})`);
    assert.strictEqual(r.kind, kind);
    assert.ok(r.text.length > 20);
  });
}

test("unknown question says information is unavailable", () => {
  const r = KB.answer(data, "What is his favourite cricket team?", "en");
  assert.strictEqual(r.matched, false);
  assert.match(r.text, /don't have that information/);
  assert.ok(r.suggestions.length >= 3);
});

test("Telugu question gets a Telugu answer", () => {
  const r = KB.answer(data, "శ్రీనివాస గురించి చెప్పండి", "te");
  assert.strictEqual(r.id, "about");
  assert.strictEqual(r.lang, "te");
  assert.match(r.text, /అనుభవం/);
});

test("Telugu rollback question", () => {
  const r = KB.answer(data, "AKS రోల్‌బ్యాక్ ఎలా పనిచేస్తుంది", "te");
  assert.strictEqual(r.id, "how-aks-delivery-platform");
  assert.strictEqual(r.lang, "te");
});

test("Telugu mode falls back to English when no Telugu answer exists", () => {
  const r = KB.answer(data, "education degree", "te");
  assert.strictEqual(r.id, "education");
  assert.strictEqual(r.lang, "en");
  assert.strictEqual(r.fallbackToEnglish, true);
});

test("every link in the knowledge base points to a built page or https URL", () => {
  for (const e of data.entries) for (const l of e.links.concat(e.lab_note ? e.lab_note.links : [])) {
    if (/^(https:\/\/|mailto:)/.test(l.href)) continue;
    const file = path.join(__dirname, "../../_site", l.href.split("#")[0]);
    assert.ok(fs.existsSync(file), `${e.id}: ${l.href}`);
  }
});

test("no private contact details in the knowledge base", () => {
  const s = JSON.stringify(data);
  assert.ok(!/996657718|gollapudi\.srinu18@/.test(s));
});
