/* Navigation and the demo walkthrough player. */
(function () {
  "use strict";
  var toggle = document.querySelector(".menu-toggle");
  var nav = document.getElementById("site-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(open));
    });
    nav.addEventListener("click", function (e) {
      if (e.target.tagName === "A") { nav.classList.remove("open"); toggle.setAttribute("aria-expanded", "false"); }
    });
  }

  var stage = document.querySelector("[data-walkthrough]");
  if (!stage) return;
  var scenes = Array.prototype.slice.call(stage.querySelectorAll(".scene"));
  var caption = stage.querySelector(".caption");
  var count = stage.querySelector(".count");
  var bar = stage.querySelector(".progress span");
  var prev = stage.querySelector("[data-prev]");
  var next = stage.querySelector("[data-next]");
  var play = stage.querySelector("[data-play]");
  var i = 0;
  var timer = null;
  var params = new URLSearchParams(location.search);
  var seconds = parseFloat(params.get("seconds") || "6");

  function show(n) {
    i = Math.max(0, Math.min(scenes.length - 1, n));
    scenes.forEach(function (s, k) {
      s.classList.toggle("active", k === i);
      s.setAttribute("aria-hidden", k === i ? "false" : "true");
    });
    caption.textContent = scenes[i].getAttribute("data-caption");
    count.textContent = "Scene " + (i + 1) + " of " + scenes.length;
    bar.style.width = ((i + 1) / scenes.length * 100) + "%";
    prev.disabled = i === 0;
    next.disabled = i === scenes.length - 1;
    document.body.setAttribute("data-scene", String(i + 1));
    if (i === scenes.length - 1) stopPlay(true);
  }
  function stopPlay(done) {
    if (timer) clearInterval(timer);
    timer = null;
    play.textContent = done ? "↺ Replay" : "▶ Play";
    play.setAttribute("aria-pressed", "false");
    if (done) document.body.setAttribute("data-finished", "true");
  }
  function startPlay() {
    if (i === scenes.length - 1) show(0);
    play.textContent = "❚❚ Pause";
    play.setAttribute("aria-pressed", "true");
    timer = setInterval(function () { show(i + 1); }, seconds * 1000);
  }
  prev.addEventListener("click", function () { stopPlay(); show(i - 1); });
  next.addEventListener("click", function () { stopPlay(); show(i + 1); });
  play.addEventListener("click", function () { if (timer) stopPlay(); else startPlay(); });
  document.addEventListener("keydown", function (e) {
    if (e.target.closest && e.target.closest("input, textarea, select")) return;
    if (e.key === "ArrowRight") { stopPlay(); show(i + 1); }
    if (e.key === "ArrowLeft") { stopPlay(); show(i - 1); }
  });
  show(0);
  if (params.get("autoplay") === "1") { document.body.classList.add("rec"); startPlay(); }
})();
