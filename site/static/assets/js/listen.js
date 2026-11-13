/* "Listen to Portfolio" (home page hero).
 * One button plays a short spoken walkthrough with the browser's speech synthesis
 * (window.PortfolioSpeech in speech.js). Static, no backend, no API keys.
 * - Starts only when the visitor presses the button. Nothing plays on load.
 * - While playing, the same button reads "Stop Audio". It goes back to
 *   "Listen to Portfolio" when stopped, when the narration finishes, or on an error.
 * - Every start plays from the beginning; a new start cancels anything still queued,
 *   and callbacks from an older run are ignored, so rapid clicks never overlap.
 * - If speech is unavailable or fails, a short message and the narration text are shown.
 * - Playback only: the microphone, scrolling and the rest of the page are never touched.
 */
(function () {
  "use strict";
  var btn = document.querySelector("[data-listen]");
  if (!btn) return;
  var label = btn.querySelector("[data-listen-label]");
  var status = document.querySelector("[data-listen-status]");
  var fallback = document.querySelector("[data-listen-fallback]");
  var text = document.querySelector("[data-listen-text]").textContent.trim();
  var S = window.PortfolioSpeech;

  var IDLE = "Listen to Portfolio", PLAYING = "Stop Audio";
  var playing = false;
  var run = 0;              // id of the current run; older callbacks are ignored

  function render() {
    label.textContent = playing ? PLAYING : IDLE;
    btn.classList.toggle("is-playing", playing);
  }

  function reset(message) {
    playing = false;
    render();
    status.textContent = message || "";
  }

  function friendly(reason) {
    if (reason === "unsupported") return "Audio isn't available in this browser. Here is the narration as text.";
    if (reason === "blocked") return "Your browser blocked audio. Here is the narration as text.";
    if (reason === "no-voice") return "No voice is installed on this device. Here is the narration as text.";
    return "Audio couldn't play. Here is the narration as text.";
  }

  function showText(reason) {
    reset(friendly(reason));
    fallback.hidden = false;
  }

  function start() {
    var id = ++run;
    playing = true;
    render();
    status.textContent = "Playing the portfolio walkthrough.";
    fallback.hidden = true;
    if (!S || !S.supported) { showText("unsupported"); return; }
    S.speak(text, {
      lang: "en",
      onend: function (info) {
        if (id !== run) return;
        reset(info && info.interrupted ? "Audio stopped." : "Walkthrough finished.");
      },
      onfail: function (reason) {
        if (id !== run) return;
        showText(reason);
      }
    });
  }

  function stop() {
    run++;                  // ignore anything the stopped run still reports
    if (S) S.stop();
    reset("Audio stopped.");
  }

  btn.addEventListener("click", function () {
    if (playing) stop(); else start();
  });

  // Escape stops the narration from anywhere on the page.
  document.addEventListener("keydown", function (e) {
    if (playing && e.key === "Escape") stop();
  });

  window.__portfolioListen = { isPlaying: function () { return playing; }, text: text };
})();
