/* Spoken welcome for the portfolio home page.
 * - Uses the browser's speechSynthesis only. It never touches SpeechRecognition,
 *   so the microphone stays off until the visitor presses Voice in Ask My Portfolio.
 * - Browsers block speech before the visitor interacts, so the greeting is tried
 *   once on the first eligible click or key press, if sound is on.
 * - sessionStorage keeps two flags for this tab only: the automatic greeting has
 *   been tried, and the visitor muted it. No questions or answers are stored.
 */
(function () {
  "use strict";
  var card = document.querySelector("[data-welcome]");
  if (!card) return;

  var text = card.querySelector("[data-welcome-text]").textContent.trim();
  var playBtn = card.querySelector("[data-welcome-play]");
  var stopBtn = card.querySelector("[data-welcome-stop]");
  var muteBtn = card.querySelector("[data-welcome-mute]");
  var askLink = card.querySelector("[data-welcome-ask]");
  var statusEl = card.querySelector("[data-welcome-status]");

  var synth = ("speechSynthesis" in window && typeof window.SpeechSynthesisUtterance === "function")
    ? window.speechSynthesis : null;
  var KEY_TRIED = "portfolio.welcome.autoplayed";
  var KEY_MUTED = "portfolio.welcome.muted";
  var playing = false;
  var startTimer = null;

  function sget(k) { try { return window.sessionStorage.getItem(k); } catch (e) { return null; } }
  function sset(k, v) { try { window.sessionStorage.setItem(k, v); } catch (e) { /* storage blocked */ } }

  var muted = sget(KEY_MUTED) === "1";

  function status(t) { statusEl.textContent = t || ""; }

  function setPlaying(on) {
    playing = on;
    stopBtn.hidden = !on;
    card.classList.toggle("speaking", on);
    if (startTimer && !on) { clearTimeout(startTimer); startTimer = null; }
  }

  function renderMute() {
    muteBtn.setAttribute("aria-pressed", String(muted));
    muteBtn.textContent = muted ? "🔇 Muted" : "🔊 Sound on";
    muteBtn.setAttribute("aria-label", muted ? "Sound is muted. Turn sound on" : "Sound is on. Mute the welcome");
  }

  function pickVoice() {
    var voices = (synth && synth.getVoices && synth.getVoices()) || [];
    var en = voices.filter(function (v) { return v.lang && /^en/i.test(v.lang); });
    var pref = en.filter(function (v) { return /en-IN|en-US|en-GB/i.test(v.lang); });
    return pref[0] || en[0] || null;
  }

  function play() {
    if (!synth) {
      status("Voice playback isn't available in this browser, so the greeting is shown as text.");
      return false;
    }
    synth.cancel();
    var u = new SpeechSynthesisUtterance(text);
    u.lang = "en-US";
    var v = pickVoice();
    if (v) u.voice = v;
    u.rate = 1;
    var started = false;
    u.onstart = function () {
      started = true;
      setPlaying(true);
      status("Playing the welcome. Press Stop or Mute to end it.");
    };
    u.onend = function () { setPlaying(false); status(""); };
    u.onerror = function (e) {
      setPlaying(false);
      if (e.error === "interrupted" || e.error === "canceled") return;
      status(e.error === "not-allowed"
        ? "Your browser blocked audio. Press Play welcome to hear the greeting."
        : "The welcome couldn't play (" + e.error + "). The greeting is shown above.");
    };
    setPlaying(true);
    synth.speak(u);
    // Some browsers drop speech silently; don't leave a Stop button for audio that never started.
    startTimer = setTimeout(function () {
      if (!started && !synth.speaking) {
        setPlaying(false);
        status("No audio started. Check that sound is on, then press Play welcome.");
      }
    }, 4000);
    return true;
  }

  function stop(message) {
    if (synth && playing) synth.cancel();
    setPlaying(false);
    status(message || "");
  }

  // ---------- automatic greeting on the first eligible interaction ----------
  function eligible(e) {
    if (e.type === "keydown" && /^(Tab|Shift|Control|Alt|Meta|Escape|CapsLock|OS)$/.test(e.key)) return false;
    var t = e.target;
    if (!t || !t.closest) return true;
    if (t.closest("[data-welcome]")) return false;          // its own buttons handle themselves
    if (t.closest("[data-assistant]")) return false;        // never talk over the assistant or voice input
    if (t.closest("input, textarea, select, [contenteditable]")) return false;
    var a = t.closest("a[href]");
    if (a && a.getAttribute("href").charAt(0) !== "#") return false; // leaving the page
    return true;
  }
  function detach() {
    document.removeEventListener("click", onFirst, true);
    document.removeEventListener("keydown", onFirst, true);
  }
  function onFirst(e) {
    if (muted || sget(KEY_TRIED) === "1") { detach(); return; }
    if (!eligible(e)) return;
    detach();
    sset(KEY_TRIED, "1");
    play();
  }

  // ---------- wiring ----------
  playBtn.addEventListener("click", function () {
    sset(KEY_TRIED, "1");
    if (muted) { muted = false; sset(KEY_MUTED, "0"); renderMute(); }
    play();
  });
  stopBtn.addEventListener("click", function () { stop("Welcome stopped."); playBtn.focus(); });
  muteBtn.addEventListener("click", function () {
    muted = !muted;
    sset(KEY_MUTED, muted ? "1" : "0");
    renderMute();
    if (muted) stop("Sound off. The welcome won't play on its own. Press Play welcome to hear it.");
    else status("Sound on.");
  });
  askLink.addEventListener("click", function (e) {
    var section = document.getElementById("ask");
    var input = document.getElementById("ask-input");
    if (!section || !input) return;
    e.preventDefault();
    stop();
    section.scrollIntoView({ block: "start" });
    input.focus({ preventScroll: true });
    if (history.replaceState) history.replaceState(null, "", "#ask");
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && playing) stop("Welcome stopped.");
  });

  renderMute();
  if (!synth) {
    playBtn.disabled = true;
    playBtn.setAttribute("aria-disabled", "true");
    playBtn.title = "Voice playback isn't available in this browser";
    muteBtn.hidden = true;
    status("Voice playback isn't available in this browser, so the greeting is shown as text.");
  } else {
    if (synth.getVoices) synth.getVoices(); // some browsers load voices asynchronously
    if (!muted && sget(KEY_TRIED) !== "1") {
      document.addEventListener("click", onFirst, true);
      document.addEventListener("keydown", onFirst, true);
    }
  }

  window.__portfolioWelcome = {
    play: play, stop: stop, hasSynthesis: !!synth,
    isPlaying: function () { return playing; }
  };
})();
