/* "Ask the Portfolio" answer engine.
 *
 * Answers come only from data/agent.json (built from the resume, content.json and the
 * project architecture docs) and data/knowledge.json. No network, no API keys.
 * It keeps a small conversation state so follow-ups such as "what tools did it use?"
 * or "what were the results there?" refer to the last project or employer discussed.
 *
 * Works in the browser (window.PortfolioAgentCore) and in Node (module.exports) for tests.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.PortfolioAgentCore = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var LABELS = {
    career: "Work experience · from resume",
    lab: "Portfolio lab · synthetic data",
    incident: "Portfolio lab · simulated incident",
    guided: "Guided tour · scripted from the case study",
    meta: "About this portfolio",
    unavailable: "Not in this portfolio"
  };

  function norm(t) {
    return String(t || "").toLowerCase().replace(/[’']/g, "'").replace(/[^a-z0-9/.+#'\- ]/g, " ").replace(/\s+/g, " ").trim();
  }
  function has(q, re) { return re.test(q); }
  function sentence(list) {
    if (!list.length) return "";
    if (list.length === 1) return list[0];
    return list.slice(0, -1).join(", ") + " and " + list[list.length - 1];
  }
  function strip(t) { return String(t).replace(/\s+/g, " ").trim(); }

  // ---------- intent vocab ----------
  var ASPECTS = [
    ["walkthrough", /\b(explain|walk me through|walkthrough of|overview|describe|summar|tell me about|what is the .* project|break (it )?down)\w*/],
    ["outcome", /\b(result|outcome|metric|impact|verified|prove|achiev|numbers?|measur|success)\w*/],
    ["failure", /\b(fail(ed|ure|s)?|broke|break|went wrong|failure scenario|what happened)\w*/],
    ["recovery", /\b(recover|rollback|roll back|rolled back|mitigat|restor|fix(ed)?)\w*/],
    ["decisions", /\b(decision|trade-?off|why did (he|you) (choose|pick|use)|choices?|design choice)\w*/],
    ["scope", /\b(azure-validated|on azure|real azure|in azure|evidence|scope|validated|run on|ran on|production|real cluster|is (it|this) real|actually run)\w*/],
    ["architecture", /\b(architect\w*|diagram|design(ed)?|flow|components?|topology|structure|how is it built|how does it work|pieces)\w*/],
    ["tools", /\b(tools?|stack|technolog\w*|tech|services|languages?|used|uses|using)\w*/],
    ["implementation", /\b(implement\w*|built|build|how did he|steps|code|what did he (do|make|create)|work done|created)\w*/],
    ["problem", /\b(problem|why|challenge|pain|motivation|purpose|goal|what does it solve|solve)\w*/],
    ["demo", /\b(demo|video|recording|show me|watch)\w*/]
  ];
  var WALK_ORDER = ["problem", "architecture", "tools", "implementation", "outcome", "failure", "recovery", "decisions", "scope"];

  var PROJECT_HINTS = {
    "aks-delivery-platform": /\b(delivery platform|aks delivery|rollback|roll back|smoke test|helm|promotion|approval gate|orders api|release pipeline|pipeline project)\b/,
    "aks-observability-sre-lab": /\b(observability|sre lab|sre incident|incident lab|burn.?rate|slo lab|latency incident|opentelemetry lab|postmortem demo|incident demo|checkout)\b/,
    "azure-hub-spoke-terraform": /\b(hub.?(and.?)?spoke|terraform project|terraform lab|private dns|private endpoint|vnet|network lab|peering)\b/,
    "azure-devsecops-supply-chain": /\b(supply chain|devsecops|cosign|kyverno|sbom|image signing|signed images?|admission|trivy)\b/,
    "azure-functions-event-processing": /\b(functions?|event.?driven|queue|poison|idempoten\w*|event processing)\b/,
    "azure-dr-restore-drill": /\b(disaster recovery|dr drill|restore drill|point.?in.?time|pitr|backup|restore)\b/
  };

  var ROLE_HINTS = [
    /\b(pulse|pulse data labs?|urus)\b/,
    /\b(teknip|mitie)\b/,
    /\b(tech mahindra|lseg|london stock)\b/,
    /\b(venus|united ?health)\b/
  ];
  var RECENT = /\b(previous|last|latest|most recent|recent|current|present)\s+(employer|company|job|role|position|organi[sz]ation|work)|\bwhere (does|did) he (work|last work)|\bwho (does|did) he work for\b/;
  var CAREER = /\b(employer|company|companies|career|work history|worked at|experience at|job|role at|client|in production|professional)\b/;
  var PRONOUN = /\b(it|this|that|there|they|them|its|the project|this project|that project|that role|that job|same)\b/;
  var MORE = /^(more|tell me more|go on|continue|and\??|what else|next|keep going|anything else)\b/;

  function create(data, kb) {
    var state = { focus: null, seen: {}, turns: 0 };
    var projects = data.projects || [];
    var roles = data.roles || [];
    var prof = data.profile || {};

    function projectBySlug(s) { return projects.filter(function (p) { return p.slug === s; })[0] || null; }

    function findProject(q) {
      var best = null, bestScore = 0;
      projects.forEach(function (p) {
        var s = 0;
        (p.keywords || []).forEach(function (k) { k = norm(k); if (k.length > 2 && q.indexOf(k) !== -1) s += k.indexOf(" ") !== -1 ? 3 : 2; });
        if (q.indexOf(norm(p.title)) !== -1) s += 6;
        if (PROJECT_HINTS[p.slug] && PROJECT_HINTS[p.slug].test(q)) s += 3;
        if (s > bestScore) { best = p; bestScore = s; }
      });
      return bestScore >= 3 ? best : null;
    }

    function findRole(q) {
      for (var i = 0; i < ROLE_HINTS.length && i < roles.length; i++) if (ROLE_HINTS[i].test(q)) return i;
      if (RECENT.test(q)) return 0;
      if (/\b(first job|earliest|started (his )?career)\b/.test(q)) return roles.length - 1;
      return -1;
    }

    function aspectsOf(q) {
      var out = [];
      ASPECTS.forEach(function (a) { if (a[1].test(q)) out.push(a[0]); });
      return out;
    }

    function projectLinks(p, which) {
      var L = p.links, all = {
        case: { label: "Case study", href: L.case },
        architecture: { label: "Architecture diagrams", href: L.architecture },
        walkthrough: { label: "Interactive walkthrough", href: L.walkthrough },
        demo: { label: "Recorded demo", href: L.demo },
        source: { label: "Source code", href: L.source }
      };
      return (which || ["case", "architecture", "walkthrough"]).map(function (k) { return all[k]; });
    }

    function archText(p) {
      var t = p.architecture_summary ? p.architecture_summary + " " : "";
      var d = (p.diagrams || [])[0];
      if (d && d.components.length) t += "The " + d.title.toLowerCase() + " diagram connects: " + d.components.slice(0, 9).join(" → ") +
        (d.components.length > 9 ? ", and " + (d.components.length - 9) + " more components" : "") + ".";
      if ((p.diagrams || []).length > 1) t += " A second diagram shows the " + p.diagrams[1].title.toLowerCase() + ".";
      if (!t) t = p.environment;
      return strip(t);
    }

    function section(p, aspect) {
      switch (aspect) {
        case "problem": return { heading: "Problem", text: p.problem };
        case "architecture": return { heading: "Architecture", text: archText(p) };
        case "tools": return { heading: "Tools", text: "Tools and services: " + p.stack.join(", ") + ". Environment: " + p.environment };
        case "implementation": return { heading: "Implementation", text: p.built.join(" ") };
        case "outcome": return { heading: "Documented outcome", text: p.result + " Result type: " + p.result_scope.join(", ") +
          ". Evidence: " + p.scope.map(function (s) { return s[0] + " (" + s[1] + ")"; }).join("; ") + "." };
        case "failure": return { heading: "Failure scenario", text: p.failure };
        case "recovery": return { heading: "Recovery", text: p.recovery };
        case "decisions": return { heading: "Engineering decisions", text: p.decisions.join(" ") };
        case "scope": return { heading: "Scope and evidence", text: p.scope.map(function (s) { return s[0] + ": " + s[1]; }).join(". ") + ". " + p.evidence_gaps };
        case "demo": return { heading: "Demo", text: p.demo_intro + " The interactive walkthrough steps through the architecture, the real run output and the result. Run it yourself with: " + p.run };
      }
      return null;
    }

    function labKind(p) { return p.slug === "aks-observability-sre-lab" ? "incident" : "lab"; }
    var LAB_NOTE = "This is a portfolio lab with synthetic data, not an employer result.";

    function followupsForProject(p) {
      var seen = state.seen[p.slug] || {};
      var asks = { problem: "What problem does it solve?", architecture: "How is it architected?", tools: "What tools does it use?",
        implementation: "How was it implemented?", outcome: "What was the result?", failure: "What failure does it show?",
        recovery: "How does it recover?", decisions: "What design decisions were made?", scope: "Has it run on Azure?" };
      return WALK_ORDER.filter(function (a) { return !seen[a]; }).slice(0, 3).map(function (a) { return asks[a]; });
    }

    function answerProject(p, aspects, guided) {
      state.focus = { type: "project", slug: p.slug };
      var seen = state.seen[p.slug] = state.seen[p.slug] || {};
      var parts;
      if (guided || aspects.indexOf("walkthrough") !== -1) {
        parts = ["problem", "architecture", "tools", "implementation", "outcome"].map(function (a) { seen[a] = 1; return section(p, a); });
        return finish({
          kind: guided ? "guided" : labKind(p), title: p.title, parts: parts,
          note: LAB_NOTE + " Missing evidence: " + p.evidence_gaps,
          links: projectLinks(p, ["case", "architecture", "walkthrough", "demo"]), project: p.slug,
          spoken: (guided ? "Guided tour of " + p.title + ", scripted from the case study. " : p.title + ". ") +
            parts.map(function (s) { return s.heading + ". " + s.text; }).join(" ") + " " + LAB_NOTE
        }, followupsForProject(p));
      }
      var want = aspects.filter(function (a) { return a !== "walkthrough"; });
      if (!want.length) {
        want = ["problem", "outcome"];
      }
      parts = want.slice(0, 3).map(function (a) { seen[a] = 1; return section(p, a); });
      var links = want.indexOf("demo") !== -1 ? projectLinks(p, ["walkthrough", "demo", "case"])
        : want.indexOf("architecture") !== -1 ? projectLinks(p, ["architecture", "case", "walkthrough"]) : projectLinks(p);
      return finish({ kind: labKind(p), title: p.title, parts: parts, note: LAB_NOTE, links: links, project: p.slug }, followupsForProject(p));
    }

    function nextAspect(p) {
      var seen = state.seen[p.slug] || {};
      return WALK_ORDER.filter(function (a) { return !seen[a]; })[0] || null;
    }

    function roleName(r) { return r.title + " at " + r.company + (r.client ? " (client " + r.client + ")" : "") + ", " + r.dates; }

    function answerRole(i, q) {
      var r = roles[i];
      state.focus = { type: "role", idx: i };
      var parts = [];
      var wantsResults = /\b(result|outcome|metric|impact|achiev|number|measur)\w*/.test(q);
      var wantsTools = /\b(tool|stack|technolog|environment|used\b)\w*/.test(q);
      var recent = i === 0 && RECENT.test(q);
      var head = (recent ? "His most recent employer is " + r.company + ". " : "") + roleName(r) + (r.location ? ", " + r.location : "") + ".";
      parts.push({ heading: r.company, text: head });
      if (wantsResults) {
        var nums = r.points.filter(function (pt) { return /\d/.test(pt.replace(/24x7|L3|RTO|RPO|Dev, QA/g, "")); });
        parts.push({ heading: "Results", text: nums.length ? nums.join(" ")
          : "The resume gives no measured figures for this role, so I can't quote any. Documented responsibilities: " + r.points.slice(0, 3).join(" ") });
      } else if (wantsTools) {
        parts.push({ heading: "Environment", text: r.environment || "The resume doesn't list the tools for this role." });
      } else {
        parts.push({ heading: "What he did", text: r.points.slice(0, 5).join(" ") });
      }
      var fu = ["What were the results there?", "What tools did he use there?"];
      if (i + 1 < roles.length) fu.push("What did he do at " + roles[i + 1].company + "?");
      if (i === 0) fu.push("Is he open to remote roles?");
      return finish({ kind: "career", title: roleName(r), parts: parts,
        note: "From his resume. Portfolio lab results are separate and labelled as labs.",
        links: [{ label: "Experience", href: "index.html#experience" }, { label: "View resume", href: "resume.html" }] }, fu.slice(0, 3));
    }

    function answerRemote(q) {
      state.focus = null;
      var text = prof.remote_pref + " " + (/\b(on.?site|office|hybrid|relocat)\b/.test(q)
        ? "He is looking for remote-only roles, so on-site, hybrid or relocation roles are not what he's looking for. "
        : "") + "He is an immediate joiner, based in " + prof.location + ".";
      return finish({ kind: "career", title: "Availability", parts: [{ heading: "Availability", text: text }],
        links: [{ label: "Contact", href: "index.html#contact" }, { label: "View resume", href: "resume.html" }] },
        ["How can I contact him?", "What did he do at Pulse Data Labs?", "Explain the AKS Delivery Platform project"]);
    }

    function answerContact() {
      var text = (prof.email ? "Email him at " + prof.email + ". " : "His contact details are on his resume. ") + prof.remote_pref;
      return finish({ kind: "meta", title: "Contact", parts: [{ heading: "Contact", text: text }],
        links: (prof.email ? [{ label: "Email " + prof.email, href: "mailto:" + prof.email }] : []).concat([{ label: "View resume", href: "resume.html" }]) },
        ["Is he open to remote roles?", "What did he do at Pulse Data Labs?"]);
    }

    function whichProjects(q) {
      var terms = norm(q).replace(/\b(which|what|projects?|labs?|use[sd]?|using|show|involve[sd]?|with|have|has|the|a|an|of|in|do|does|did|portfolio)\b/g, " ")
        .split(" ").filter(function (t) { return t.length > 2; });
      if (!terms.length) return null;
      var hits = projects.filter(function (p) {
        var blob = norm([p.title, p.stack.join(" "), p.environment, p.built.join(" ")].join(" "));
        return terms.every(function (t) { return blob.indexOf(t) !== -1; });
      });
      var label = terms.join(" ");
      if (!hits.length) return finish({ kind: "unavailable", title: "No matching project",
        parts: [{ heading: "Projects", text: "None of the six portfolio labs mentions " + label + "." }], links: [{ label: "All projects", href: "index.html#projects" }] }, []);
      state.focus = hits.length === 1 ? { type: "project", slug: hits[0].slug } : state.focus;
      return finish({ kind: "lab", title: "Projects using " + label,
        parts: [{ heading: "Projects", text: "Portfolio labs that use " + label + ": " + sentence(hits.map(function (p) { return p.title; })) + "." }],
        note: hits.length > 1 ? "These are portfolio labs with synthetic data, not employer results." : LAB_NOTE, links: hits.slice(0, 4).map(function (p) { return { label: p.title, href: p.links.case }; }) },
        hits.slice(0, 2).map(function (p) { return "Explain the " + p.title + " project"; }));
    }

    function knows(q, original) {
      var re = /(?:know|use[sd]?|experience (?:with|in)|worked (?:with|on)|familiar with|skilled in|has he used)\s+(.+?)[?.!]*$/i;
      var m = re.exec(q);
      if (!m) return null;
      var om = re.exec(String(original || "").trim());
      var term = ((om && om[1]) || m[1]).replace(/^(the|any|a|an)\s+/i, "").trim();
      if (!term || term.length < 2 || PRONOUN.test(norm(term))) return null;
      var t = norm(term);
      var where = [];
      roles.forEach(function (r) { if (norm(r.environment + " " + r.points.join(" ")).indexOf(t) !== -1) where.push("work at " + r.company + " (" + r.dates + ")"); });
      var inSkills = (data.skills || []).some(function (g) { return g.items.some(function (i) { return norm(i).indexOf(t) !== -1; }); });
      var labs = projects.filter(function (p) { return norm(p.stack.join(" ") + " " + p.environment + " " + p.built.join(" ")).indexOf(t) !== -1; });
      if (!where.length && !inSkills && !labs.length) {
        return finish({ kind: "unavailable", title: "Not listed", parts: [{ heading: term, text: "I don't see " + term + " in his resume or the portfolio labs, so I can't confirm it." }],
          links: [{ label: "Skills", href: "index.html#skills" }] }, ["What are his core skills?"]);
      }
      var parts = [];
      if (where.length || inSkills) parts.push({ heading: "Work experience", text: where.length ? "The resume lists " + term + " in his " + sentence(where) + "." : term + " is listed in his resume skills." });
      if (labs.length) parts.push({ heading: "Portfolio labs", text: "Portfolio labs that use it: " + sentence(labs.map(function (p) { return p.title; })) + "." });
      return finish({ kind: where.length || inSkills ? "career" : "lab", title: term, parts: parts,
        note: "Work experience comes from the resume; lab use is synthetic portfolio work.",
        links: labs.slice(0, 3).map(function (p) { return { label: p.title, href: p.links.case }; }).concat([{ label: "Skills", href: "index.html#skills" }]) }, []);
    }

    function finish(res, followups) {
      res.label = LABELS[res.kind] || LABELS.meta;
      res.followups = followups || [];
      res.text = res.parts.map(function (p) { return p.text; }).join(" ") + (res.note ? " " + res.note : "");
      if (!res.spoken) res.spoken = res.parts.map(function (p) { return p.text; }).join(" ");
      res.grounded = res.kind !== "unavailable";
      return res;
    }

    function fromKb(question) {
      if (!kb || !root_kb()) return null;
      var r = root_kb().answer(kb, question, "en");
      if (!r.matched) return null;
      var kindMap = { career: "career", lab: "lab", incident: "incident", meta: "meta" };
      var parts = [{ heading: "", text: r.text }];
      if (r.labNote) parts.push({ heading: "Portfolio lab", text: r.labNote.text });
      return finish({ kind: kindMap[r.kind] || "meta", title: "", parts: parts, links: (r.links || []).concat(r.labNote ? r.labNote.links : []).slice(0, 5) },
        (kb.samples || []).slice(0, 2));
    }
    function root_kb() {
      if (typeof module === "object" && module.exports) { try { return require("./kb.js"); } catch (e) { return null; } }
      return (typeof self !== "undefined" && self.PortfolioKB) || null;
    }

    function unavailable(q) {
      var sal = /\b(salary|ctc|compensation|pay|rate|expected|visa|passport|age|married|notice period)\b/.test(q);
      var text = sal && /notice period/.test(q) ? "The portfolio doesn't give a notice period; it says he is an immediate joiner."
        : "I don't have that information in this portfolio" + (sal ? " — it isn't in his resume or the case studies." : ".") +
          " I can answer from his resume (employers, roles, dates, skills, availability) and the six portfolio labs (problem, architecture, tools, implementation and documented results).";
      return finish({ kind: "unavailable", title: "Not in this portfolio", parts: [{ heading: "", text: text }],
        links: [{ label: "Contact", href: "index.html#contact" }] },
        ["What did he do at Pulse Data Labs?", "Explain the AKS Delivery Platform project", "Is he open to remote roles?"]);
    }

    function ask(question) {
      state.turns++;
      var q = norm(question);
      if (!q) return unavailable(q);
      var aspects = aspectsOf(q);

      if (/\b(remote|on.?site|onsite|hybrid|relocat\w*|work from home|wfh|availab\w*|open to|looking for|join(ing)?|immediate)\b/.test(q) && !findProject(q)) return answerRemote(q);
      if (/\b(contact|email|e-mail|reach (him|out)|get in touch|hire him|phone)\b/.test(q)) return answerContact();

      var ri = findRole(q);
      if (ri >= 0 && roles.length) return answerRole(ri, q);

      if (/\bwhich (projects?|labs?)\b|\bprojects? (that )?(use|using|with)\b/.test(q)) { var w = whichProjects(q); if (w) return w; }

      var p = findProject(q);
      if (p) return answerProject(p, aspects, false);
      if (/\b(srinivasa|gollapudi|about him|who is he|who is this|introduce (him|yourself)|his background)\b/.test(q)) {
        state.focus = null; var ab = fromKb("tell me about srinivasa"); if (ab) return ab;
      }
      var k = knows(q, question); if (k) return k;

      // follow-ups on the last project or employer
      var f = state.focus;
      var followUp = aspects.length || PRONOUN.test(q) || MORE.test(q);
      if (f && followUp) {
        if (f.type === "project") {
          var fp = projectBySlug(f.slug);
          if (MORE.test(q) && !aspects.length) { var na = nextAspect(fp); if (na) return answerProject(fp, [na], false); }
          if (aspects.length) return answerProject(fp, aspects, false);
        } else if (f.type === "role" && (aspects.length || PRONOUN.test(q) || MORE.test(q))) {
          return answerRole(f.idx, q);
        }
      }
      if (CAREER.test(q) && /\b(employer|compan|career|work history|clients?)\b/.test(q) && roles.length) {
        state.focus = null;
        return finish({ kind: "career", title: "Work history", parts: [{ heading: "Work history",
          text: "11+ years in IT. " + roles.map(roleName).join(". ") + "." }],
          links: [{ label: "Experience", href: "index.html#experience" }, { label: "View resume", href: "resume.html" }] },
          roles.slice(0, 2).map(function (r) { return "What did he do at " + r.company + "?"; }));
      }
      var kbr = fromKb(question);
      if (kbr) return kbr;
      return unavailable(q);
    }

    function explain(slug) {
      var p = projectBySlug(slug);
      if (!p) return unavailable("");
      return answerProject(p, ["walkthrough"], true);
    }

    return { ask: ask, explain: explain, state: state, labels: LABELS };
  }

  return { create: create, LABELS: LABELS, norm: norm };
});
