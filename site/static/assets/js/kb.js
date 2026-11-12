/* Local question matching for "Ask My Portfolio".
 * Pure functions, no network. Works in the browser (window.PortfolioKB)
 * and in Node (module.exports) for tests.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.PortfolioKB = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var STOP = new Set(("a an the is are was were be been of in on at to for and or with about me tell show " +
    "what how does do did can could you your his he him my i please give explain who which where when " +
    "this that it its from by as").split(" "));

  function normalize(text) {
    return String(text || "")
      .toLowerCase()
      .normalize("NFC")
      .replace(/[^\p{L}\p{N}\p{M}\s\/.+-]/gu, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function tokens(text) {
    return normalize(text).split(" ").filter(function (t) { return t && !STOP.has(t); });
  }

  // Words that signal the visitor wants a demo or a project rather than career history.
  var DEMO_WORDS = ["demo", "video", "show me", "walkthrough", "డెమో", "వీడియో", "చూపించు", "చూపించండి"];
  var PROJECT_WORDS = ["project", "lab", "portfolio", "built", "ప్రాజెక్ట్", "ల్యాబ్"];

  function score(entry, q, qTokens) {
    var s = 0;
    var kws = (entry.keywords || []).concat(entry.keywords_te || []);
    for (var i = 0; i < kws.length; i++) {
      var k = normalize(kws[i]);
      if (k && q.indexOf(k) !== -1) s += k.indexOf(" ") !== -1 ? 4 : 3;
    }
    var titleTokens = new Set(tokens(entry.title));
    qTokens.forEach(function (t) { if (titleTokens.has(t)) s += 1; });
    var wantsDemo = DEMO_WORDS.some(function (w) { return q.indexOf(w) !== -1; });
    var wantsProject = PROJECT_WORDS.some(function (w) { return q.indexOf(w) !== -1; });
    if (s > 0 && wantsDemo && entry.intent === "demo") s += 3;
    if (s > 0 && !wantsDemo && entry.intent === "demo") s -= 1;
    if (s > 0 && wantsProject && entry.kind !== "career") s += 1;
    return s;
  }

  var THRESHOLD = 3;

  function answer(kb, question, lang) {
    var q = normalize(question);
    var qTokens = tokens(question);
    var best = null;
    var bestScore = 0;
    (kb.entries || []).forEach(function (e) {
      var s = score(e, q, qTokens);
      if (s > bestScore) { best = e; bestScore = s; }
    });
    var te = lang === "te";
    if (!best || bestScore < THRESHOLD) {
      return {
        matched: false,
        id: null,
        kind: "unavailable",
        text: te ? kb.unavailable_te : kb.unavailable,
        lang: te ? "te" : "en",
        links: [],
        suggestions: kb.samples || []
      };
    }
    var hasTe = te && best.answer_te;
    return {
      matched: true,
      id: best.id,
      kind: best.kind,
      score: bestScore,
      text: hasTe ? best.answer_te : best.answer,
      lang: hasTe ? "te" : "en",
      fallbackToEnglish: te && !best.answer_te,
      links: best.links || []
    };
  }

  return { normalize: normalize, tokens: tokens, answer: answer, THRESHOLD: THRESHOLD };
});
