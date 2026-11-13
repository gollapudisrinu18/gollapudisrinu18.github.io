/* Audio intro and the diagram-based Portfolio Tour (home page).
 * - Audio plays only after the visitor clicks Play intro or Play narration. Nothing plays on load
 *   or on a first click elsewhere.
 * - The intro has a transcript and Play / Pause / Resume / Stop controls.
 * - The tour shows captions synchronised with the selected diagram; narration is optional
 *   (Play narration, then Pause / Resume), and each step change cancels the previous narration.
 * - Narration uses PortfolioSpeech (speech synthesis only). The microphone is never used.
 * - sessionStorage keeps one flag for this tab: tour narration muted.
 */
(function () {
  "use strict";
  var bar = document.querySelector("[data-tour]");
  var intro = document.querySelector("[data-intro]");
  if (!bar || !intro) return;
  var S = window.PortfolioSpeech || { supported: false, speak: function (t, o) { if (o && o.onfail) o.onfail("unsupported"); },
    stop: function () {}, pause: function () { return false; }, resume: function () { return false; }, isPaused: function () { return false; } };
  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var KEY_MUTED = "portfolio.welcome.muted";
  function sget(k) { try { return window.sessionStorage.getItem(k); } catch (e) { return null; } }
  function sset(k, v) { try { window.sessionStorage.setItem(k, v); } catch (e) { /* storage blocked */ } }

  function friendly(reason) {
    if (reason === "blocked") return "Your browser needs a click before it can play sound. Press Play again to listen.";
    if (reason === "unsupported") return "This browser can't read text aloud. The transcript is shown instead.";
    if (reason === "no-voice") return "No suitable voice is installed on this device. The transcript is shown instead.";
    return "Audio couldn't start in this browser. The text is shown here, and you can try again.";
  }

  // Only one owner speaks at a time: "intro" or "tour".
  var owner = null;

  // ---------------- intro ----------------
  var introText = intro.querySelector("[data-intro-text]").textContent.trim();
  var introPlay = document.querySelector("[data-intro-play]");          // hero button
  var introToggle = intro.querySelector("[data-intro-toggle]");         // play / pause / resume
  var introStop = intro.querySelector("[data-intro-stop]");
  var introStatus = intro.querySelector("[data-intro-status]");
  var transcriptBtn = document.querySelector("[data-intro-transcript]");
  var introState = "idle";   // idle | loading | playing | paused | failed

  function renderIntro() {
    var label = { idle: "Play", loading: "Pause", playing: "Pause", paused: "Resume", failed: "Try again" }[introState];
    introToggle.textContent = label;
    introToggle.setAttribute("aria-label", label + " intro audio");
    introStop.disabled = introState === "idle" || introState === "failed";
    introPlay.setAttribute("aria-pressed", String(introState === "playing" || introState === "loading"));
    intro.classList.toggle("speaking", introState === "playing");
  }
  function showIntro(open) {
    intro.hidden = !open;
    transcriptBtn.setAttribute("aria-expanded", String(open));
    transcriptBtn.textContent = open ? "Hide transcript" : "Intro transcript";
  }
  function playIntro() {
    if (owner === "tour") stopTour();
    showIntro(true);
    if (!S.supported) { introState = "failed"; introStatus.textContent = friendly("unsupported"); renderIntro(); introToggle.disabled = true; return; }
    owner = "intro";
    introState = "loading";
    introStatus.textContent = "Starting audio…";
    renderIntro();
    S.speak(introText, {
      lang: "en",
      onstart: function () { introState = "playing"; introStatus.textContent = "Playing the intro."; renderIntro(); },
      onend: function (info) {
        if (owner === "intro") owner = null;
        introState = "idle";
        introStatus.textContent = info && info.interrupted ? "Intro stopped." : "Intro finished.";
        renderIntro();
      },
      onfail: function (reason) {
        if (owner === "intro") owner = null;
        introState = "failed";
        introStatus.textContent = friendly(reason);
        renderIntro();
      }
    });
  }
  function toggleIntro() {
    if (introState === "playing" || introState === "loading") {
      if (S.pause()) { introState = "paused"; introStatus.textContent = "Intro paused."; renderIntro(); }
    } else if (introState === "paused") {
      if (S.resume()) { introState = "playing"; introStatus.textContent = "Playing the intro."; renderIntro(); }
    } else {
      playIntro();
    }
  }
  function stopIntro() {
    if (owner === "intro") S.stop();
    owner = null;
    introState = "idle";
    renderIntro();
  }

  introPlay.addEventListener("click", function () {
    if (introState === "playing" || introState === "loading" || introState === "paused") { stopIntro(); introStatus.textContent = "Intro stopped."; return; }
    playIntro();
  });
  introToggle.addEventListener("click", toggleIntro);
  introStop.addEventListener("click", function () { stopIntro(); introStatus.textContent = "Intro stopped."; introToggle.focus(); });
  transcriptBtn.addEventListener("click", function () { showIntro(intro.hidden); });

  // ---------------- tour ----------------
  var stepEl = bar.querySelector("[data-tour-step]");
  var capEl = bar.querySelector("[data-tour-caption]");
  var noteEl = bar.querySelector("[data-tour-note]");
  var backBtn = bar.querySelector("[data-tour-back]");
  var nextBtn = bar.querySelector("[data-tour-next]");
  var stopBtn = bar.querySelector("[data-tour-stop]");
  var playNarr = bar.querySelector("[data-tour-play]");
  var muteBtn = bar.querySelector("[data-mute]");
  var muted = sget(KEY_MUTED) === "1";
  var narrating = false;     // the visitor asked for narration
  var narrState = "idle";    // idle | playing | paused | failed
  var step = -1;

  var STEPS = [
    { key: "delivery", title: "Delivery",
      say: "Delivery. A change runs through Azure Pipelines, which tests it and builds one image in Azure Container Registry. " +
           "That same image is deployed to Dev and QA, then waits at an approval gate before Production. " +
           "After every deployment a smoke test runs; if it fails, Helm rolls back to the previous revision and later stages never run." },
    { key: "infrastructure", title: "Infrastructure",
      say: "Infrastructure. Terraform builds a hub-and-spoke network. Each spoke is its own VNet with network security groups. " +
           "Storage has public access turned off and is reached through a private endpoint, and the private DNS zone is linked to every VNet." },
    { key: "reliability", title: "Reliability",
      say: "Reliability. The checkout service sends metrics and traces. A latency SLO with burn-rate alerts pages the on-call engineer. " +
           "Traces point to the slow dependency, a cache fallback mitigates it, and a blameless postmortem records what to fix." },
    { key: "projects", title: "Explore",
      say: "That's the tour. These are portfolio labs with case studies, recorded demos and interactive walkthroughs. " +
           "Open a project, view the resume, or press Ask the Portfolio to ask a question by voice or text. " +
           "He is open to remote-only Senior Azure DevOps Engineer and SRE roles." }
  ];

  function renderNarr() {
    var label = narrState === "playing" ? "Pause narration"
      : narrState === "paused" ? "Resume narration"
      : narrState === "failed" ? "Try audio again"
      : (narrating ? "Replay narration" : "Play narration");
    playNarr.textContent = label;
    playNarr.setAttribute("aria-pressed", String(narrState === "playing"));
    muteBtn.setAttribute("aria-pressed", String(muted));
    muteBtn.textContent = muted ? "Unmute" : "Mute";
    muteBtn.setAttribute("aria-label", muted ? "Narration is muted. Turn sound on" : "Mute narration");
  }

  function selectTab(key) {
    var tab = document.querySelector('[data-tab="' + key + '"]');
    if (tab && window.PortfolioTabs) window.PortfolioTabs.select(tab, false);
  }
  function highlight(key) {
    document.querySelectorAll(".tour-focus").forEach(function (n) { n.classList.remove("tour-focus"); });
    var target = key === "projects" ? document.getElementById("projects") : document.getElementById("arch-" + key);
    if (!target) return;
    target.classList.add("tour-focus");
    target.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
  }

  function narrate() {
    var at = step;
    noteEl.textContent = "";
    if (owner === "tour") S.stop();
    if (muted || !narrating) { narrState = "idle"; renderNarr(); return; }
    if (owner === "intro") { stopIntro(); }
    owner = "tour";
    narrState = "playing";
    noteEl.textContent = "Starting narration…";
    renderNarr();
    S.speak(STEPS[step].say, {
      lang: "en",
      onstart: function () { if (step === at) noteEl.textContent = "Narrating: " + STEPS[at].title + "."; },
      onend: function () {
        if (step !== at) return;
        if (owner === "tour") owner = null;
        narrState = "idle";
        if (/^(Narrating|Starting)/.test(noteEl.textContent)) noteEl.textContent = "";
        renderNarr();
      },
      onfail: function (reason) {
        if (step !== at) return;
        if (owner === "tour") owner = null;
        narrState = reason === "unsupported" ? "idle" : "failed";
        noteEl.textContent = friendly(reason);
        renderNarr();
      }
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
    if (owner === "intro") stopIntro();
    narrating = false;
    narrState = "idle";
    bar.hidden = false;
    document.body.classList.add("touring");
    show(0);
    nextBtn.focus({ preventScroll: true });
  }
  function stopTour() {
    if (owner === "tour") S.stop();
    if (owner === "tour") owner = null;
    narrating = false;
    narrState = "idle";
    step = -1;
    bar.hidden = true;
    document.body.classList.remove("touring");
    document.querySelectorAll(".tour-focus").forEach(function (n) { n.classList.remove("tour-focus"); });
  }

  document.querySelectorAll("[data-tour-start]").forEach(function (b) { b.addEventListener("click", startTour); });
  nextBtn.addEventListener("click", function () {
    if (step === STEPS.length - 1) { stopTour(); document.querySelector("[data-tour-start]").focus({ preventScroll: true }); return; }
    show(step + 1);
  });
  backBtn.addEventListener("click", function () { show(step - 1); });
  stopBtn.addEventListener("click", function () { stopTour(); document.querySelector("[data-tour-start]").focus({ preventScroll: true }); });
  playNarr.addEventListener("click", function () {
    if (narrState === "playing") { if (S.pause()) { narrState = "paused"; noteEl.textContent = "Narration paused."; renderNarr(); } return; }
    if (narrState === "paused") { if (S.resume()) { narrState = "playing"; noteEl.textContent = "Narrating: " + STEPS[step].title + "."; renderNarr(); } return; }
    if (muted) { muted = false; sset(KEY_MUTED, "0"); }
    narrating = true;
    narrate();
  });
  muteBtn.addEventListener("click", function () {
    muted = !muted;
    sset(KEY_MUTED, muted ? "1" : "0");
    if (muted) { narrating = false; if (owner === "tour") { S.stop(); owner = null; } narrState = "idle"; noteEl.textContent = "Narration muted. Captions stay on screen."; }
    else noteEl.textContent = "";
    renderNarr();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    if (step >= 0) stopTour();
    else if (owner === "intro") { stopIntro(); introStatus.textContent = "Intro stopped."; }
  });

  if (!S.supported) {
    [introPlay, playNarr].forEach(function (b) { b.disabled = true; b.setAttribute("aria-disabled", "true"); });
    muteBtn.hidden = true;
    introPlay.title = "This browser can't read text aloud. Use the transcript.";
  }
  renderIntro();
  renderNarr();

  window.__portfolioTour = { start: startTour, stop: stopTour, step: function () { return step; }, steps: STEPS.length };
})();
