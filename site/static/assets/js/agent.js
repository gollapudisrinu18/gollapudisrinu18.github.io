/* "Ask the Portfolio" voice agent - available on every page.
 *
 * - Ask by voice (SpeechRecognition, when the browser has it) or by typing.
 * - Hear the answer (speechSynthesis via PortfolioSpeech) and read it as text.
 * - Follow-up questions keep the context of the last project or employer.
 * - "Explain this project" buttons ([data-explain="<slug>"]) play a scripted guided tour
 *   of that project: problem, architecture, tools, implementation and documented outcome.
 * - Answers are grounded in data/agent.json and data/knowledge.json (built from the resume
 *   and case studies). If <body data-agent-endpoint> is set, the question is also sent to that
 *   serverless endpoint (which holds any AI credentials); otherwise nothing leaves the page.
 * - The microphone starts only when the visitor presses the mic button.
 */
(function () {
  "use strict";
  var body = document.body;
  var base = body.getAttribute("data-root") || "./";
  var endpoint = (body.getAttribute("data-agent-endpoint") || "").trim();
  var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition || null;
  var S = window.PortfolioSpeech || { supported: false, speak: function (t, o) { if (o && o.onfail) o.onfail("unsupported"); }, stop: function () {}, isSpeaking: function () { return false; } };

  var engine = null, loading = null, rec = null, listening = false, history = [], lastTrigger = null;

  function el(tag, attrs, text) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "class") n.className = attrs[k]; else if (k === "html") n.innerHTML = attrs[k]; else n.setAttribute(k, attrs[k]);
    });
    if (text != null) n.textContent = text;
    return n;
  }

  // ---------- markup ----------
  var MIC_SVG = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false"><path fill="currentColor" d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2Z"/></svg>';
  var fab = el("button", { class: "agent-fab", type: "button", "aria-controls": "ask", "aria-expanded": "false", "aria-label": "Ask the Portfolio (voice or text)", "data-agent-open": "" });
  fab.innerHTML = MIC_SVG + '<span>Ask the Portfolio</span>';

  var panel = el("section", { class: "agent", id: "ask", role: "dialog", "aria-modal": "false", "aria-labelledby": "agent-title", hidden: "" });
  panel.innerHTML =
    '<header class="agent-head">' +
      '<div><h2 id="agent-title">Ask the Portfolio</h2>' +
      '<p class="agent-mode" data-agent-mode>' + (endpoint ? "AI answers grounded in the resume and case studies" : "Answers from the resume and case studies") + '</p></div>' +
      '<button type="button" class="btn small ghost agent-close" data-agent-close aria-label="Close Ask the Portfolio">✕</button>' +
    '</header>' +
    '<div class="agent-log" role="log" aria-live="polite" aria-label="Conversation" data-agent-log></div>' +
    '<div class="agent-chips" data-agent-chips aria-label="Suggested questions"></div>' +
    '<p class="agent-status" role="status" aria-live="polite" data-agent-status></p>' +
    '<form class="agent-form" data-agent-form autocomplete="off">' +
      '<label class="sr-only" for="agent-input">Your question</label>' +
      '<input id="agent-input" type="text" maxlength="300" placeholder="Ask about experience, projects, availability…" data-agent-input>' +
      '<button type="button" class="btn agent-mic" data-agent-mic aria-pressed="false" aria-label="Ask by voice">' + MIC_SVG + '</button>' +
      '<button type="submit" class="btn primary">Ask</button>' +
    '</form>' +
    '<div class="agent-opts">' +
      '<label><input type="checkbox" data-agent-speak checked> Read answers aloud</label>' +
      '<label><input type="checkbox" data-agent-handsfree> Hands-free follow-ups</label>' +
      '<button type="button" class="btn small ghost" data-agent-stop disabled>Stop audio</button>' +
      '<button type="button" class="btn small ghost" data-agent-clear>Clear</button>' +
    '</div>' +
    '<p class="agent-privacy">The microphone starts only when you press the mic button; your browser\'s speech service may process the audio. ' +
      (endpoint ? "Questions are sent to the portfolio's AI endpoint to write the answer and are not stored on this page. "
                : "Answers are produced in this page from the portfolio content; nothing is sent to a server. ") +
      'Employer facts come from the resume; project results are portfolio labs with synthetic data.</p>';

  document.body.appendChild(fab);
  document.body.appendChild(panel);

  var $ = function (s) { return panel.querySelector(s); };
  var log = $("[data-agent-log]"), chips = $("[data-agent-chips]"), statusEl = $("[data-agent-status]");
  var form = $("[data-agent-form]"), input = $("[data-agent-input]"), micBtn = $("[data-agent-mic]");
  var speakBox = $("[data-agent-speak]"), handsBox = $("[data-agent-handsfree]"), stopBtn = $("[data-agent-stop]");

  function setStatus(t, mode) { statusEl.textContent = t || ""; statusEl.className = "agent-status" + (mode ? " " + mode : ""); }

  // ---------- open / close ----------
  function open(focusInput) {
    if (!panel.hidden) { if (focusInput) input.focus(); return; }
    lastTrigger = document.activeElement;
    panel.hidden = false;
    body.classList.add("agent-open");
    document.querySelectorAll("[data-agent-open]").forEach(function (b) { b.setAttribute("aria-expanded", "true"); });
    load().then(function () {
      if (!log.children.length) greet();
    });
    if (focusInput !== false) input.focus();
  }
  function close() {
    stopAll(true);
    panel.hidden = true;
    body.classList.remove("agent-open");
    document.querySelectorAll("[data-agent-open]").forEach(function (b) { b.setAttribute("aria-expanded", "false"); });
    if (lastTrigger && lastTrigger.focus) lastTrigger.focus();
  }

  function load() {
    if (loading) return loading;
    setStatus("Loading the portfolio content…");
    loading = Promise.all([
      fetch(base + "data/agent.json").then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }),
      fetch(base + "data/knowledge.json").then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })
    ]).then(function (res) {
      engine = window.PortfolioAgentCore.create(res[0], res[1]);
      engine.data = res[0];
      setStatus(Recognition ? "Ready. Type a question or press the mic to ask by voice." : "Ready. Type your question (voice input isn't available in this browser).");
    }).catch(function () {
      loading = null;
      setStatus("The portfolio content couldn't load. Please check your connection and try again.", "error");
      throw new Error("load");
    });
    return loading;
  }

  function greet() {
    var p = engine.data.profile;
    var msg = el("div", { class: "msg bot" });
    msg.appendChild(el("p", null, "Hi! I can answer questions about " + p.name + "'s experience and his six portfolio projects. " + p.remote_pref));
    log.appendChild(msg);
    showChips(["What did he do at Pulse Data Labs?", "Explain the AKS Delivery Platform project", "Is he open to remote roles?", "Which projects use Terraform?"]);
  }

  // ---------- rendering ----------
  function showChips(list) {
    chips.innerHTML = "";
    (list || []).forEach(function (q) {
      var b = el("button", { type: "button", class: "btn small chip" }, q);
      b.addEventListener("click", function () { ask(q, { via: "chip" }); });
      chips.appendChild(b);
    });
  }

  function linkRow(links) {
    var row = el("div", { class: "msg-links" });
    links.forEach(function (l) {
      if (!l || !l.href) return;
      var a = el("a", null, l.label);
      a.href = /^(https?:|mailto:)/.test(l.href) ? l.href : base + l.href;
      row.appendChild(a);
    });
    return row;
  }

  var KIND_CLASS = { career: "", lab: "teal", incident: "warn", guided: "teal", meta: "", unavailable: "warn", ai: "teal" };

  function render(res, opts) {
    var msg = el("div", { class: "msg bot", "data-kind": res.kind });
    var kind = el("div", { class: "kind" });
    kind.appendChild(el("span", { class: "badge " + (KIND_CLASS[res.kind] || "") }, res.label));
    if (opts && opts.ai) kind.appendChild(el("span", { class: "badge teal" }, "AI answer · grounded in portfolio content"));
    msg.appendChild(kind);
    if (res.title) msg.appendChild(el("p", { class: "msg-title" }, res.title));
    if (opts && opts.ai) {
      msg.appendChild(el("p", { class: "msg-text" }, opts.ai));
    } else {
      res.parts.forEach(function (p) {
        var para = el("p", { class: "msg-text" });
        if (p.heading && res.parts.length > 1) { para.appendChild(el("strong", null, p.heading + ": ")); }
        para.appendChild(document.createTextNode(p.text));
        msg.appendChild(para);
      });
    }
    if (res.note) msg.appendChild(el("p", { class: "msg-note" }, res.note));
    if (opts && opts.fallbackNote) msg.appendChild(el("p", { class: "msg-note" }, opts.fallbackNote));
    if (res.links && res.links.length) msg.appendChild(linkRow(res.links));
    if (S.supported) {
      var row = el("div", { class: "msg-links" });
      var play = el("button", { type: "button", class: "btn small ghost listen", "aria-label": "Listen to this answer" }, "▶ Listen");
      play.addEventListener("click", function () { speak(opts && opts.ai ? opts.ai : res.spoken, res.kind === "guided"); });
      row.appendChild(play);
      msg.appendChild(row);
    }
    log.appendChild(msg);
    log.scrollTop = Math.max(0, msg.offsetTop - log.offsetTop - 8);
    showChips(res.followups);
    return msg;
  }

  // ---------- speech ----------
  function speak(text, guided) {
    stopListening();
    S.speak(text, {
      lang: "en",
      onstart: function () { stopBtn.disabled = false; setStatus(guided ? "Playing the guided tour (scripted from the case study)…" : "Reading the answer aloud…", "speaking"); },
      onend: function (info) {
        stopBtn.disabled = true;
        if (info && info.interrupted) return;
        if (handsBox.checked && Recognition && !panel.hidden) { setStatus("Listening for your follow-up…", "listening"); startListening(); }
        else setStatus("Ask a follow-up by typing, with the mic, or pick a suggestion.");
      },
      onfail: function (reason) {
        stopBtn.disabled = true;
        setStatus({
          unsupported: "This browser can't read answers aloud. The answer is shown as text.",
          blocked: "Your browser blocked audio until you interact with the page. Press ▶ Listen to hear the answer.",
          "no-voice": "No voice is installed for audio playback. The answer is shown as text.",
          failed: "Audio couldn't play. The answer is shown as text; press ▶ Listen to try again."
        }[reason] || "Audio couldn't play. The answer is shown as text.", "error");
      }
    });
  }

  // ---------- asking ----------
  function aiAnswer(question, res) {
    var ctrl = window.AbortController ? new AbortController() : null;
    var timer = setTimeout(function () { if (ctrl) ctrl.abort(); }, 15000);
    return fetch(endpoint, {
      method: "POST", headers: { "Content-Type": "application/json" }, signal: ctrl ? ctrl.signal : undefined,
      body: JSON.stringify({ question: question, history: history.slice(-4), focus: engine.state.focus,
        hint: { kind: res.kind, title: res.title, text: res.text } })
    }).then(function (r) {
      clearTimeout(timer);
      if (!r.ok) throw new Error("status " + r.status);
      return r.json();
    }).then(function (j) {
      if (!j || typeof j.answer !== "string" || !j.answer.trim()) throw new Error("empty");
      return j.answer.trim();
    });
  }

  function ask(question, opts) {
    question = String(question || "").trim();
    if (!question) return;
    opts = opts || {};
    open(false);
    load().then(function () {
      var u = el("div", { class: "msg user" });
      u.appendChild(el("span", null, question));
      log.appendChild(u);
      var res = engine.ask(question);
      var shouldSpeak = opts.via === "voice" || speakBox.checked;
      if (endpoint) {
        setStatus("Thinking…");
        aiAnswer(question, res).then(function (text) {
          render(res, { ai: text });
          history.push({ q: question, a: text });
          setStatus("");
          if (shouldSpeak) speak(text, false);
        }).catch(function () {
          render(res, { fallbackNote: "The AI service didn't respond, so this answer comes straight from the portfolio content." });
          history.push({ q: question, a: res.text });
          if (shouldSpeak) speak(res.spoken, false);
        });
        return;
      }
      render(res);
      history.push({ q: question, a: res.text });
      if (shouldSpeak) speak(res.spoken, res.kind === "guided"); else setStatus("Answered. Press ▶ Listen to hear it, or ask a follow-up.");
    });
  }

  function explain(slug) {
    open(false);
    load().then(function () {
      var p = (engine.data.projects || []).filter(function (x) { return x.slug === slug; })[0];
      var u = el("div", { class: "msg user" });
      u.appendChild(el("span", null, "Explain this project" + (p ? ": " + p.title : "")));
      log.appendChild(u);
      var res = engine.explain(slug);
      render(res);
      history.push({ q: "Explain " + slug, a: res.text });
      if (speakBox.checked) speak(res.spoken, true); else setStatus("Guided tour shown as text. Press ▶ Listen to hear it.");
    });
  }

  // ---------- voice input ----------
  function stopListening() {
    if (rec && listening) { try { rec.abort(); } catch (e) { /* ignore */ } }
    listening = false;
    micBtn.setAttribute("aria-pressed", "false");
    micBtn.classList.remove("on");
  }

  function startListening() {
    if (!Recognition) { setStatus("Voice input isn't available in this browser. Please type your question.", "error"); return; }
    S.stop();
    stopListening();
    rec = new Recognition();
    rec.lang = "en-US";
    rec.interimResults = true;
    rec.continuous = false;
    rec.maxAlternatives = 1;
    var finalText = "";
    rec.onstart = function () {
      listening = true;
      micBtn.setAttribute("aria-pressed", "true");
      micBtn.classList.add("on");
      setStatus("Listening… ask your question. Press the mic again to stop.", "listening");
    };
    rec.onresult = function (e) {
      var interim = "";
      for (var i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) finalText += e.results[i][0].transcript; else interim += e.results[i][0].transcript;
      }
      input.value = finalText || interim;
    };
    rec.onerror = function (e) {
      var msg = {
        "not-allowed": "Microphone permission was denied. Allow it in your browser's site settings, or type your question.",
        "service-not-allowed": "Voice input is blocked in this browser. Please type your question.",
        "no-speech": "I didn't hear anything. Press the mic and try again, or type.",
        "audio-capture": "No microphone was found. Please type your question.",
        "network": "The browser's speech service couldn't be reached. Please type your question."
      }[e.error];
      if (e.error !== "aborted") setStatus(msg || "Voice input stopped. Please type your question.", "error");
      if (e.error === "not-allowed" || e.error === "service-not-allowed") handsBox.checked = false;
    };
    rec.onend = function () {
      var wasListening = listening;
      listening = false;
      micBtn.setAttribute("aria-pressed", "false");
      micBtn.classList.remove("on");
      if (finalText.trim()) { input.value = ""; ask(finalText, { via: "voice" }); }
      else if (wasListening && /listening/.test(statusEl.className)) setStatus("Stopped listening.");
    };
    try { rec.start(); } catch (err) { setStatus("Voice input couldn't start. Please type your question.", "error"); }
  }

  function stopAll(quiet) {
    stopListening();
    S.stop();
    stopBtn.disabled = true;
    if (!quiet) setStatus("Stopped.");
  }

  // ---------- wiring ----------
  form.addEventListener("submit", function (e) { e.preventDefault(); var q = input.value; input.value = ""; ask(q, { via: "text" }); });
  micBtn.addEventListener("click", function () { if (listening) stopAll(); else { open(false); load().then(startListening); } });
  stopBtn.addEventListener("click", function () { stopAll(); });
  $("[data-agent-clear]").addEventListener("click", function () {
    stopAll(true); log.innerHTML = ""; history = [];
    if (engine) { engine.state.focus = null; engine.state.seen = {}; greet(); }
    setStatus("Conversation cleared.");
  });
  $("[data-agent-close]").addEventListener("click", close);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !panel.hidden) { e.preventDefault(); close(); } });
  if (!Recognition) { micBtn.disabled = true; micBtn.title = "Voice input isn't available in this browser"; handsBox.disabled = true; }
  if (!S.supported) { speakBox.checked = false; speakBox.disabled = true; }

  document.addEventListener("click", function (e) {
    var t = e.target.closest ? e.target.closest("[data-agent-open],[data-explain]") : null;
    if (!t) return;
    e.preventDefault();
    if (t.hasAttribute("data-explain")) explain(t.getAttribute("data-explain"));
    else if (!panel.hidden && t === fab) close();
    else open(true);
  });
  if (location.hash === "#ask") open(false);

  window.PortfolioAgent = { open: open, close: close, ask: ask, explain: explain,
    get engine() { return engine; }, hasRecognition: !!Recognition, endpoint: endpoint };
})();
