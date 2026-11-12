/* Welcome panel and the diagram-based Portfolio Tour (home page).
 * - Narration uses PortfolioSpeech (speech synthesis only). The microphone is never used.
 * - The welcome is attempted once per browser tab session: straight away if the browser
 *   allows audio, otherwise on the visitor's first click or key press. Muting or using the
 *   welcome/tour controls also counts, so it is never repeated automatically.
 * - Captions are always shown, so the tour works muted or without audio support.
 * - sessionStorage holds only two flags: welcome tried, and muted.
 */
(function () {
  "use strict";
  var welcome = document.querySelector("[data-welcome]");
  var bar = document.querySelector("[data-tour]");
  if (!welcome || !bar) return;
  var S = window.PortfolioSpeech || { supported: false, speak: function (t, o) { if (o && o.onfail) o.onfail("unsupported"); }, stop: function () {}, activated: function () { return true; } };

  var text = welcome.querySelector("[data-welcome-text]").textContent.trim();
  var wStatus = welcome.querySelector("[data-welcome-status]");
  var playBtn = welcome.querySelector("[data-welcome-play]");
  var muteBtns = Array.prototype.slice.call(document.querySelectorAll("[data-mute]"));
  var stepEl = bar.querySelector("[data-tour-step]");
  var capEl = bar.querySelector("[data-tour-caption]");
  var noteEl = bar.querySelector("[data-tour-note]");
  var backBtn = bar.querySelector("[data-tour-back]");
  var nextBtn = bar.querySelector("[data-tour-next]");
  var stopBtn = bar.querySelector("[data-tour-stop]");
  var retryBtn = bar.querySelector("[data-tour-retry]");
  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var KEY_TRIED = "portfolio.welcome.autoplayed";
  var KEY_MUTED = "portfolio.welcome.muted";
  function sget(k) { try { return window.sessionStorage.getItem(k); } catch (e) { return null; } }
  function sset(k, v) { try { window.sessionStorage.setItem(k, v); } catch (e) { /* storage blocked */ } }
  var muted = sget(KEY_MUTED) === "1";

  var STEPS = [
    { key: "delivery", title: "Delivery",
      say: "Delivery. A change runs through Azure Pipelines, which tests it and builds one image in Azure Container Registry. " +
           "That same image is promoted to Dev, QA and Production on AKS, with an approval gate before Production. " +
           "Every deployment is smoke-tested, and a failed release rolls back to the previous version." },
    { key: "infrastructure", title: "Infrastructure",
      say: "Infrastructure. Terraform builds a hub-and-spoke network. Each spoke is its own VNet with network security groups. " +
           "Storage has public access turned off and is reached through a private endpoint, and the private DNS zone is linked to every VNet." },
    { key: "reliability", title: "Reliability",
      say: "Reliability. The checkout service sends metrics and traces. A latency SLO with burn-rate alerts pages the on-call engineer. " +
           "Traces point to the slow dependency, a cache fallback mitigates it, and a blameless postmortem records what to fix." },
    { key: "projects", title: "Explore",
      say: "That's the tour. These are portfolio labs with case studies and walkthroughs. " +
           "Open a project, view the resume, or ask the assistant a question." }
  ];
  var step = -1;

  // ---------- helpers ----------
  function friendly(reason) {
    if (reason === "blocked") return "Your browser needs a click before it can play sound. Press the button again to listen.";
    if (reason === "unsupported") return "This browser can't read text aloud, so the captions are shown instead.";
    return "Audio couldn't start in this browser. The text is shown here, and you can try again.";
  }
  function renderMute() {
    muteBtns.forEach(function (b) {
      b.setAttribute("aria-pressed", String(muted));
      b.textContent = muted ? "Unmute" : "Mute";
      b.setAttribute("aria-label", muted ? "Sound is off. Turn sound on" : "Turn sound off");
    });
  }
  function setMuted(on) {
    muted = on;
    sset(KEY_MUTED, on ? "1" : "0");
    renderMute();
    if (on) { S.stop(); welcome.classList.remove("speaking"); }
  }

  // ---------- welcome ----------
  function playWelcome(auto) {
    if (!S.supported) { wStatus.textContent = friendly("unsupported"); return; }
    wStatus.textContent = "";
    S.speak(text, {
      lang: "en",
      onstart: function () { sset(KEY_TRIED, "1"); welcome.classList.add("speaking"); wStatus.textContent = "Playing the welcome. Press Mute to stop."; },
      onend: function () { welcome.classList.remove("speaking"); if (/Playing/.test(wStatus.textContent)) wStatus.textContent = ""; },
      onfail: function (reason) {
        welcome.classList.remove("speaking");
        if (auto && reason === "blocked") { armFirstInteraction(); return; }  // wait for a click, say nothing
        if (auto) { sset(KEY_TRIED, "1"); return; }
        wStatus.textContent = friendly(reason);
      }
    });
  }

  function eligible(e) {
    if (e.type === "keydown" && /^(Tab|Shift|Control|Alt|Meta|Escape|CapsLock|OS)$/.test(e.key)) return false;
    var t = e.target;
    if (!t || !t.closest) return true;
    if (t.closest("[data-welcome], [data-tour], [data-tour-start], [data-assistant]")) return false;
    if (t.closest("input, textarea, select, [contenteditable], video")) return false;
    var a = t.closest("a[href]");
    if (a && a.getAttribute("href").charAt(0) !== "#") return false;  // leaving the page
    return true;
  }
  var armed = false;
  function onFirst(e) {
    if (muted || sget(KEY_TRIED) === "1" || step >= 0) { disarm(); return; }
    if (!eligible(e)) return;
    disarm();
    sset(KEY_TRIED, "1");
    playWelcome(false);
  }
  function armFirstInteraction() {
    if (armed) return;
    armed = true;
    document.addEventListener("click", onFirst, true);
    document.addEventListener("keydown", onFirst, true);
  }
  function disarm() {
    armed = false;
    document.removeEventListener("click", onFirst, true);
    document.removeEventListener("keydown", onFirst, true);
  }

  // ---------- tour ----------
  function selectTab(key) {
    var tab = document.querySelector('[data-tab="' + key + '"]');
    if (tab && window.PortfolioTabs) window.PortfolioTabs.select(tab, false);
  }
  function highlight(key) {
    document.querySelectorAll(".tour-focus").forEach(function (n) { n.classList.remove("tour-focus"); });
    var target = key === "projects" ? document.getElementById("projects") : document.getElementById("arch-" + key);
    if (!target) return;
    target.classList.add("tour-focus");
    // Scroll the diagram itself to the top so as much of it as possible sits above the tour bar.
    target.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
  }
  function narrate() {
    noteEl.textContent = "";
    retryBtn.hidden = true;
    if (muted) return;
    S.speak(STEPS[step].say, {
      lang: "en",
      onfail: function (reason) { noteEl.textContent = friendly(reason); retryBtn.hidden = reason === "unsupported"; }
    });
  }
  function show(n) {
    step = Math.max(0, Math.min(STEPS.length - 1, n));
    var s = STEPS[step];
    if (s.key !== "projects") selectTab(s.key);
    highlight(s.key);
    stepEl.textContent = s.title + " · " + (step + 1) + " of " + STEPS.length;
    capEl.textContent = s.say;
    backBtn.disabled = step === 0;
    nextBtn.textContent = step === STEPS.length - 1 ? "Finish" : "Next";
    narrate();
  }
  function startTour() {
    disarm();
    sset(KEY_TRIED, "1");
    welcome.classList.remove("speaking");
    bar.hidden = false;
    document.body.classList.add("touring");
    show(0);
    nextBtn.focus({ preventScroll: true });
  }
  function stopTour(message) {
    S.stop();
    step = -1;
    bar.hidden = true;
    document.body.classList.remove("touring");
    document.querySelectorAll(".tour-focus").forEach(function (n) { n.classList.remove("tour-focus"); });
    if (message) wStatus.textContent = message;
  }

  // ---------- wiring ----------
  document.querySelectorAll("[data-tour-start]").forEach(function (b) { b.addEventListener("click", startTour); });
  nextBtn.addEventListener("click", function () {
    if (step === STEPS.length - 1) { stopTour("Tour finished. You can start it again at any time."); return; }
    show(step + 1);
  });
  backBtn.addEventListener("click", function () { show(step - 1); });
  stopBtn.addEventListener("click", function () {
    stopTour("Tour stopped.");
    var start = welcome.querySelector("[data-tour-start]");
    if (start) start.focus({ preventScroll: true });
  });
  retryBtn.addEventListener("click", narrate);
  playBtn.addEventListener("click", function () {
    disarm();
    sset(KEY_TRIED, "1");
    if (muted) setMuted(false);
    playWelcome(false);
  });
  muteBtns.forEach(function (b) {
    b.addEventListener("click", function () {
      disarm();
      sset(KEY_TRIED, "1");
      setMuted(!muted);
      if (step >= 0 && !muted) narrate();
      if (step < 0) wStatus.textContent = muted ? "Sound is off. Captions and text stay on screen." : "Sound is on.";
    });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && step >= 0) stopTour("Tour stopped.");
  });

  renderMute();
  if (!S.supported) {
    playBtn.disabled = true;
    playBtn.setAttribute("aria-disabled", "true");
    muteBtns.forEach(function (b) { b.hidden = true; });
    wStatus.textContent = "This browser can't read text aloud. The tour still works with captions.";
  } else if (!muted && sget(KEY_TRIED) !== "1") {
    if (S.activated()) playWelcome(true);   // the browser already allows audio
    else armFirstInteraction();
  }

  window.__portfolioTour = { start: startTour, stop: stopTour, step: function () { return step; }, steps: STEPS.length };
})();
