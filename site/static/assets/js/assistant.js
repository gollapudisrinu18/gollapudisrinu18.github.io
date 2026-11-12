/* "Ask My Portfolio" - voice and text assistant.
 * - Answers come from data/knowledge.json via PortfolioKB (local matching, no API keys).
 * - Voice input: Web Speech API SpeechRecognition (when the browser has it).
 * - Voice output: speechSynthesis (when the browser has it).
 * - Nothing is written to localStorage, cookies or a server. The conversation
 *   exists only in this page and disappears on reload.
 */
(function () {
  "use strict";
  var root = document.querySelector("[data-assistant]");
  if (!root) return;

  var base = document.body.getAttribute("data-root") || "./";
  var $ = function (sel) { return root.querySelector(sel); };
  var log = $(".log");
  var form = $(".ask-form");
  var input = $("#ask-input");
  var micBtn = $(".mic");
  var stopBtn = $(".stop");
  var speakBox = $("#speak-answers");
  var langSel = $("#ask-lang");
  var statusEl = $(".status");
  var statusText = $(".status-text");
  var clearBtn = $(".clear");

  var KB = null;
  var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition || null;
  var synth = ("speechSynthesis" in window) ? window.speechSynthesis : null;
  var rec = null;
  var listening = false;

  var LANGS = {
    en: { rec: "en-US", label: "English", placeholder: "Ask about experience, projects or demos" },
    te: { rec: "te-IN", label: "తెలుగు", placeholder: "తెలుగు లేదా English లో అడగండి" }
  };
  var KIND_LABEL = {
    career: ["Career history · from resume", ""],
    lab: ["Portfolio lab result", "teal"],
    incident: ["Simulated incident", "warn"],
    meta: ["About this portfolio", ""],
    unavailable: ["Not in this portfolio", "warn"]
  };

  function lang() { return langSel ? langSel.value : "en"; }

  function setStatus(text, mode) {
    statusText.textContent = text;
    statusEl.className = "status" + (mode ? " " + mode : "");
    var busy = mode === "listening" || mode === "speaking";
    stopBtn.disabled = !busy;
  }

  function addMessage(who, nodes) {
    var div = document.createElement("div");
    div.className = "msg " + who;
    nodes.forEach(function (n) { div.appendChild(n); });
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function pickVoice(code) {
    if (!synth) return null;
    var voices = synth.getVoices() || [];
    var exact = voices.filter(function (v) { return v.lang && v.lang.toLowerCase().indexOf(code) === 0; });
    if (!exact.length) return null;
    var pref = exact.filter(function (v) { return /en-IN|en-US|en-GB|te-IN/i.test(v.lang); });
    return (pref[0] || exact[0]);
  }

  function speak(text, code) {
    if (!synth) {
      setStatus("Audio playback isn't available in this browser. The answer is shown as text.", "error");
      return false;
    }
    var voice = pickVoice(code);
    if (!voice && code === "te") {
      setStatus("No Telugu voice is installed on this device, so the answer is shown as text only.", "error");
      return false;
    }
    synth.cancel();
    var u = new SpeechSynthesisUtterance(text);
    u.lang = code === "te" ? "te-IN" : "en-US";
    if (voice) u.voice = voice;
    u.rate = 1;
    u.onstart = function () { setStatus("Speaking the answer… press Stop to end.", "speaking"); };
    u.onend = function () { setStatus("Ready. Type or press the microphone to ask.", ""); };
    u.onerror = function (e) {
      if (e.error !== "interrupted" && e.error !== "canceled") setStatus("Audio playback failed (" + e.error + ").", "error");
    };
    synth.speak(u);
    return true;
  }

  function renderAnswer(res) {
    var nodes = [];
    var kind = KIND_LABEL[res.kind] || KIND_LABEL.meta;
    var badge = el("span", "badge " + kind[1], kind[0]);
    var kindRow = el("div", "kind");
    kindRow.appendChild(badge);
    nodes.push(kindRow);
    var p = el("p", "", res.text);
    p.style.margin = "0";
    p.lang = res.lang;
    nodes.push(p);
    if (res.fallbackToEnglish) nodes.push(el("div", "note", "తెలుగు సమాధానం అందుబాటులో లేదు; English లో చూపిస్తున్నాం."));
    if (res.links && res.links.length) {
      var links = el("div", "msg-links");
      res.links.forEach(function (l) {
        var a = el("a", "", l.label);
        a.href = /^https?:/.test(l.href) ? l.href : base + l.href;
        links.appendChild(a);
      });
      nodes.push(links);
    }
    if (!res.matched && res.suggestions && res.suggestions.length) {
      var s = el("div", "note", "Try: " + res.suggestions.slice(0, 3).join(" · "));
      nodes.push(s);
    }
    if (synth) {
      var play = el("button", "btn small ghost", "▶ Listen");
      play.type = "button";
      play.setAttribute("aria-label", "Read this answer aloud");
      play.addEventListener("click", function () { speak(res.text, res.lang); });
      var row = el("div", "msg-links");
      row.appendChild(play);
      nodes.push(row);
    }
    addMessage("bot", nodes);
  }

  function ask(question) {
    question = (question || "").trim();
    if (!question) return;
    addMessage("user", [el("span", "", question)]);
    if (!KB) {
      renderAnswer({ matched: false, kind: "unavailable", text: "The knowledge base is still loading. Please try again in a moment.", lang: "en", links: [] });
      return;
    }
    var res = window.PortfolioKB.answer(KB, question, lang());
    renderAnswer(res);
    if (speakBox && speakBox.checked) speak(res.text, res.lang);
    else setStatus("Answered. Press ▶ Listen to hear it, or ask another question.", "");
  }

  // ---------------- voice input ----------------
  function micUnavailable(reason, mode) {
    micBtn.disabled = true;
    micBtn.setAttribute("aria-disabled", "true");
    micBtn.title = reason;
    setStatus(reason, mode || "");
  }

  function startListening() {
    if (!Recognition) return;
    if (synth) synth.cancel();
    rec = new Recognition();
    rec.lang = LANGS[lang()].rec;
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    rec.continuous = false;
    var finalText = "";
    rec.onstart = function () {
      listening = true;
      micBtn.setAttribute("aria-pressed", "true");
      setStatus("Listening (" + LANGS[lang()].label + ")… speak now. Press Stop to cancel.", "listening");
    };
    rec.onresult = function (e) {
      var interim = "";
      for (var i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) finalText += e.results[i][0].transcript;
        else interim += e.results[i][0].transcript;
      }
      input.value = finalText || interim;
      if (interim) setStatus("Heard: “" + interim + "”", "listening");
    };
    rec.onerror = function (e) {
      var msg = {
        "not-allowed": "Microphone permission was denied. Allow it in your browser's site settings, or type your question.",
        "service-not-allowed": "Voice input is blocked in this browser. Please type your question.",
        "no-speech": "I didn't hear anything. Press the microphone and try again, or type.",
        "audio-capture": "No microphone was found. Please type your question.",
        "network": "The browser's speech service couldn't be reached. Please type your question.",
        "language-not-supported": LANGS[lang()].label + " voice input isn't supported in this browser. Please type your question."
      }[e.error] || ("Voice input stopped (" + e.error + "). Please type your question.");
      if (e.error !== "aborted") setStatus(msg, "error");
      if (e.error === "not-allowed" || e.error === "service-not-allowed") micUnavailable(msg, "error");
    };
    rec.onend = function () {
      listening = false;
      micBtn.setAttribute("aria-pressed", "false");
      if (statusEl.classList.contains("listening")) setStatus("Ready.", "");
      if (finalText.trim()) { ask(finalText); input.value = ""; }
    };
    try { rec.start(); } catch (err) { setStatus("Couldn't start voice input: " + err.message, "error"); }
  }

  function stopAll() {
    if (rec && listening) { try { rec.abort(); } catch (e) { /* ignore */ } }
    if (synth) synth.cancel();
    micBtn.setAttribute("aria-pressed", "false");
    setStatus("Stopped. Type or press the microphone to ask.", "");
  }

  // ---------------- wiring ----------------
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    ask(input.value);
    input.value = "";
  });
  root.querySelectorAll("[data-sample]").forEach(function (b) {
    b.addEventListener("click", function () { ask(b.getAttribute("data-sample")); });
  });
  micBtn.addEventListener("click", function () {
    if (listening) { stopAll(); return; }
    startListening(); // starts only after this user click
  });
  stopBtn.addEventListener("click", stopAll);
  clearBtn.addEventListener("click", function () {
    log.innerHTML = "";
    stopAll();
    setStatus("Conversation cleared.", "");
  });
  if (langSel) langSel.addEventListener("change", function () {
    input.placeholder = LANGS[lang()].placeholder;
    input.lang = lang();
    if (lang() === "te" && synth && synth.getVoices().length && !pickVoice("te")) {
      setStatus("Telugu voice input works in supported browsers. This device has no Telugu voice for playback, so answers appear as text.", "");
    } else {
      setStatus("Language: " + LANGS[lang()].label + ".", "");
    }
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && (listening || (synth && synth.speaking))) stopAll();
  });

  if (!Recognition) micUnavailable("Voice input isn't available in this browser. You can type your question instead.");
  else if (navigator.permissions && navigator.permissions.query) {
    navigator.permissions.query({ name: "microphone" }).then(function (p) {
      if (p.state === "denied") micUnavailable("Microphone access is blocked for this site. Allow it in site settings, or type your question.", "error");
    }).catch(function () { /* not supported for microphone in some browsers */ });
  }
  if (!synth && speakBox) {
    speakBox.disabled = true;
    speakBox.closest("label").title = "Audio playback isn't available in this browser";
  }
  if (synth) synth.getVoices(); // warm up voice list (some browsers load it async)

  fetch(base + "data/knowledge.json")
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (data) {
      KB = data;
      if (!statusEl.classList.contains("error")) setStatus("Ready. Type a question or press the microphone.", "");
    })
    .catch(function () { setStatus("Couldn't load the portfolio knowledge base.", "error"); });

  window.__portfolioAssistant = { ask: ask, hasRecognition: !!Recognition, hasSynthesis: !!synth };
})();
