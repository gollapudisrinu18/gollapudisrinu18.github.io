/* Shared text-to-speech for the welcome, the portfolio tour and Ask My Portfolio.
 *
 * Browser speech can fail in several ways; each is handled here so pages only see
 * a friendly reason ("blocked", "no-voice", "failed", "unsupported"):
 *  - Chrome and Safari refuse speech until the visitor has clicked or pressed a key
 *    ("not-allowed", or no events at all).                          -> "blocked"
 *  - Network voices (for example "Google US English") can fail with
 *    "synthesis-failed" or "network", and stop after about 15 seconds.
 *    Local voices are preferred, text is spoken a sentence at a time, and a
 *    failed sentence is retried once with the browser's default voice. -> "failed"
 *  - Voices load asynchronously; speak() waits briefly for them.
 *  - Utterances that are garbage-collected never fire "end"; they are kept referenced.
 *  - Speech can keep playing after navigation; it is cancelled on pagehide.
 * Only one narration plays at a time: starting a new one stops the previous one.
 * This module never touches SpeechRecognition (the microphone).
 */
(function () {
  "use strict";
  var synth = ("speechSynthesis" in window && typeof window.SpeechSynthesisUtterance === "function")
    ? window.speechSynthesis : null;
  var voices = [];
  var current = null;          // the active job
  var keep = [];               // keep utterances referenced until they finish
  var seq = 0;

  function loadVoices() {
    try { voices = (synth && synth.getVoices && synth.getVoices()) || []; } catch (e) { voices = []; }
    return voices;
  }
  var ready = new Promise(function (resolve) {
    if (!synth) return resolve([]);
    if (loadVoices().length) return resolve(voices);
    var done = false;
    function finish() { if (!done) { done = true; resolve(loadVoices()); } }
    try { synth.addEventListener ? synth.addEventListener("voiceschanged", finish) : (synth.onvoiceschanged = finish); } catch (e) { /* ignore */ }
    setTimeout(finish, 1200);
  });

  function voiceFor(lang, avoid) {
    var list = loadVoices().filter(function (v) { return v !== avoid; });
    var code = lang === "te" ? "te" : "en";
    var match = list.filter(function (v) { return v.lang && v.lang.toLowerCase().replace("_", "-").indexOf(code) === 0; });
    if (!match.length) return null;
    var local = match.filter(function (v) { return v.localService !== false; });
    var pool = local.length ? local : match;
    if (code === "en") {
      var pref = pool.filter(function (v) { return /en-(IN|US|GB)/i.test(v.lang.replace("_", "-")); });
      if (pref.length) pool = pref;
    }
    return pool.filter(function (v) { return v.default; })[0] || pool[0];
  }

  function hasVoice(lang) { return !!voiceFor(lang); }

  function sentences(text) {
    var parts = String(text).match(/[^.!?。]+[.!?。]*\s*/g) || [String(text)];
    var out = [];
    parts.forEach(function (p) {
      p = p.trim();
      if (!p) return;
      if (out.length && (out[out.length - 1].length + p.length) < 120) out[out.length - 1] += " " + p;
      else out.push(p);
    });
    return out;
  }

  function activated() {
    var ua = navigator.userActivation;
    return ua ? ua.hasBeenActive : true;
  }

  function stop() {
    var job = current;
    current = null;
    if (job) { job.cancelled = true; clearTimeout(job.timer); }
    if (synth && (synth.speaking || synth.pending || synth.paused)) { try { synth.cancel(); synth.resume(); } catch (e) { /* ignore */ } }
    if (job && job.opts.onend) job.opts.onend({ interrupted: true });
  }

  /* speak(text, {lang, onstart, onend(info), onfail(reason)}) -> job id
   * onend is called once when narration finishes or is stopped.
   * onfail is called instead of onend when nothing could be played. */
  function speak(text, opts) {
    opts = opts || {};
    if (!synth) { if (opts.onfail) opts.onfail("unsupported"); return null; }
    var hadJob = !!current;
    if (current) stop();
    var job = { id: ++seq, opts: opts, parts: sentences(text), i: 0, started: false, retried: false, cancelled: false };
    current = job;
    ready.then(function () {
      if (job.cancelled) return;
      if (opts.lang === "te" && !hasVoice("te")) { current = null; if (opts.onfail) opts.onfail("no-voice"); return; }
      // Chrome (notably on Windows) can drop or stall an utterance queued right after cancel():
      // let the engine settle, make sure it is not left paused, then speak.
      var busy = synth.speaking || synth.pending;
      if (busy) { try { synth.cancel(); } catch (e) { /* ignore */ } }
      setTimeout(function () {
        if (job.cancelled) return;
        try { if (synth.paused) synth.resume(); } catch (e) { /* ignore */ }
        next(job);
      }, busy || hadJob ? 200 : 0);
    });
    return job.id;
  }

  function fail(job, reason) {
    if (job.cancelled) return;
    job.cancelled = true;
    clearTimeout(job.timer);
    if (current === job) current = null;
    try { synth.cancel(); } catch (e) { /* ignore */ }
    if (job.opts.onfail) job.opts.onfail(reason);
  }

  function next(job, voiceOverride) {
    if (job.cancelled) return;
    if (job.i >= job.parts.length) {
      if (current === job) current = null;
      if (job.opts.onend) job.opts.onend({ interrupted: false });
      return;
    }
    var u = new SpeechSynthesisUtterance(job.parts[job.i]);
    u.lang = job.opts.lang === "te" ? "te-IN" : "en-US";
    var v = voiceOverride === undefined ? voiceFor(job.opts.lang) : voiceOverride;
    if (v) { u.voice = v; u.lang = v.lang; }
    u.rate = 1;
    keep.push(u);
    var settled = false;
    function release() { settled = true; clearTimeout(job.timer); keep = keep.filter(function (x) { return x !== u; }); }
    u.onstart = function () {
      clearTimeout(job.timer);
      if (job.cancelled) return;
      if (!job.started) { job.started = true; if (job.opts.onstart) job.opts.onstart(); }
    };
    u.onend = function () { if (settled) return; release(); if (!job.cancelled) { job.i++; next(job); } };
    u.onerror = function (e) {
      if (settled) return;
      release();
      if (job.cancelled) return;
      var err = e && e.error;
      if (err === "interrupted" || err === "canceled") return;           // stopped on purpose
      if (err === "not-allowed") return fail(job, "blocked");
      if (!job.retried) {                                                  // retry once with the default voice
        job.retried = true;
        return setTimeout(function () { if (!job.cancelled) next(job, null); }, 250);
      }
      fail(job, "failed");
    };
    // Watchdog: some browsers drop speech silently. The first utterance of a session can take
    // several seconds to start on Windows, and some voices never fire "start" at all, so speech
    // that the browser reports as playing counts as started.
    job.timer = setTimeout(function () {
      if (settled || job.cancelled || job.started || job.paused) return;
      if (synth.speaking && !synth.pending) { u.onstart(); return; }
      if (!activated()) return fail(job, "blocked");
      if (!job.retried) {
        job.retried = true;
        try { synth.cancel(); } catch (e) { /* ignore */ }
        release();
        setTimeout(function () {
          if (job.cancelled) return;
          try { if (synth.paused) synth.resume(); } catch (e) { /* ignore */ }
          next(job, null);
        }, 250);
        return;
      }
      release();
      fail(job, "failed");
    }, 6000);
    try {
      if (synth.paused) synth.resume();
      synth.speak(u);
    } catch (err) {
      release();
      fail(job, "failed");
    }
  }

  function isSpeaking() { return !!current; }

  // Pause and resume the current narration. The start watchdog is suspended while paused.
  function pause() {
    if (!current || !synth) return false;
    current.paused = true;
    clearTimeout(current.timer);
    try { synth.pause(); } catch (e) { /* ignore */ }
    return true;
  }
  function resume() {
    if (!current || !synth) return false;
    current.paused = false;
    try { synth.resume(); } catch (e) { /* ignore */ }
    return true;
  }
  function isPaused() { return !!(current && current.paused); }

  if (synth) {
    loadVoices();
    window.addEventListener("pagehide", function () { if (current || synth.speaking) { current = null; try { synth.cancel(); } catch (e) { /* ignore */ } } });
  }

  window.PortfolioSpeech = {
    supported: !!synth, ready: ready, speak: speak, stop: stop, pause: pause, resume: resume,
    isSpeaking: isSpeaking, isPaused: isPaused, hasVoice: hasVoice, activated: activated, _sentences: sentences
  };
})();
