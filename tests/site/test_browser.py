"""Browser checks for the portfolio site (Playwright + Chrome).

  python site/build_site.py && python -m http.server 8765 --directory _site &
  SITE_URL=http://127.0.0.1:8765/ python -m pytest tests/site/test_browser.py
"""
import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("SITE_URL", "http://127.0.0.1:8765/")
CHROME = os.environ.get("CHROME_PATH", "/usr/bin/google-chrome")
SITE = Path(__file__).resolve().parents[2] / "_site"

# Fake SpeechRecognition used to drive each voice path deterministically.
FAKE_SR = """
window.__rec = [];
class FakeRec {
  constructor(){ window.__rec.push(this); this.lang=''; }
  start(){
    const mode = window.__srMode;
    setTimeout(() => {
      if (mode === 'denied') { this.onerror && this.onerror({error:'not-allowed'}); this.onend && this.onend(); return; }
      if (mode === 'unsupported-lang') { this.onerror && this.onerror({error:'language-not-supported'}); this.onend && this.onend(); return; }
      this.onstart && this.onstart();
      if (mode === 'speak') setTimeout(() => {
        const r = [{transcript: window.__phrase}]; r.isFinal = true;
        this.onresult && this.onresult({resultIndex:0, results:[r]});
        this.onend && this.onend();
      }, 150);
    }, 30);
  }
  abort(){ this.aborted = true; this.onend && this.onend(); }
  stop(){ this.onend && this.onend(); }
}
window.SpeechRecognition = FakeRec; window.webkitSpeechRecognition = FakeRec;
"""
FAKE_TTS = """
window.__spoken = [];
const voices = window.__voices || [{lang:'en-US', name:'Test English'}];
Object.defineProperty(window, 'speechSynthesis', {value: {
  speaking:false, getVoices(){ return voices; }, cancel(){ window.__cancelled=(window.__cancelled||0)+1; },
  speak(u){ window.__spoken.push({text:u.text, lang:u.lang}); u.onstart && u.onstart(); setTimeout(()=>u.onend&&u.onend(), 50); }
}});
window.SpeechSynthesisUtterance = function(t){ this.text=t; };
"""
NO_SPEECH = "delete window.SpeechRecognition; delete window.webkitSpeechRecognition;"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        yield b
        b.close()


def test_no_autoplay_before_interaction(browser):
    page = home(browser, "window.__srMode='speak';" + FAKE_SR, FAKE_TTS)
    page.wait_for_timeout(500)
    assert page.evaluate("window.__rec.length") == 0
    assert page.evaluate("window.__spoken.length") == 0


def test_keyboard_navigation(browser):
    page = browser.new_page()
    page.goto(BASE + "index.html")
    page.keyboard.press("Tab")
    expect(page.locator(".skip-link")).to_be_focused()
    page.goto(BASE + "demos/aks-delivery-platform.html")
    expect(page.locator(".count")).to_have_text(re.compile("Scene 1 of"))
    page.keyboard.press("ArrowRight")
    expect(page.locator(".count")).to_have_text(re.compile("Scene 2 of"))
    page.keyboard.press("ArrowLeft")
    expect(page.locator(".count")).to_have_text(re.compile("Scene 1 of"))


def test_mobile_menu(browser):
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(BASE + "index.html")
    expect(page.locator("#site-nav")).to_be_hidden()
    page.click(".menu-toggle")
    expect(page.locator("#site-nav")).to_be_visible()
    page.click("#site-nav a[href$='#projects']")
    expect(page.locator("#site-nav")).to_be_hidden()


def test_reduced_motion(browser):
    ctx = browser.new_context(reduced_motion="reduce")
    page = ctx.new_page()
    page.goto(BASE + "index.html")
    assert page.evaluate("getComputedStyle(document.documentElement).scrollBehavior") == "auto"


def test_internal_links_and_images_resolve():
    bad = []
    for html_file in SITE.rglob("*.html"):
        text = html_file.read_text(encoding="utf-8")
        for ref in re.findall(r'(?:href|src)="([^"#?]+)', text):
            if re.match(r"^(https?:|data:|mailto:)", ref):
                continue
            if not (html_file.parent / ref).resolve().exists():
                bad.append(f"{html_file.relative_to(SITE)} -> {ref}")
    assert not bad, bad


def test_diagrams_render_in_browser(browser):
    page = browser.new_page()
    for slug in ["aks-delivery-platform", "azure-hub-spoke-terraform", "aks-observability-sre-lab",
                 "azure-devsecops-supply-chain", "azure-functions-event-processing", "azure-dr-restore-drill"]:
        page.goto(BASE + f"projects/{slug}.html")
        imgs = page.locator(".diagram img")
        n = imgs.count()
        assert n >= (2 if slug in ("aks-delivery-platform", "azure-hub-spoke-terraform",
                                   "aks-observability-sre-lab", "azure-devsecops-supply-chain") else 1)
        for i in range(n):
            imgs.nth(i).scroll_into_view_if_needed()
            assert page.evaluate("(el) => el.complete && el.naturalWidth > 0", imgs.nth(i).element_handle())


# ---------------- portfolio redesign: hero, architecture, case studies ----------------
HAS_RESUME = (SITE / "resume.html").exists()
SLUGS = ["aks-delivery-platform", "aks-observability-sre-lab", "azure-hub-spoke-terraform",
         "azure-devsecops-supply-chain", "azure-functions-event-processing", "azure-dr-restore-drill"]
# Speech that keeps "playing" until cancelled.
HOLD_TTS = """
window.__spoken = [];
Object.defineProperty(window, 'speechSynthesis', {value: {
  speaking:false, pending:false, getVoices(){ return [{lang:'en-US', name:'Test English', localService:true}]; },
  cancel(){ window.__cancelled=(window.__cancelled||0)+1; const u=this._u; this._u=null; this.speaking=false;
            if (u && u.onerror) u.onerror({error:'interrupted'}); },
  speak(u){ window.__spoken.push({text:u.text, lang:u.lang}); this._u=u; this.speaking=true; u.onstart && u.onstart(); },
  pause(){ window.__paused=(window.__paused||0)+1; this.paused=true; }, resume(){ window.__resumed=(window.__resumed||0)+1; this.paused=false; }
}});
window.SpeechSynthesisUtterance = function(t){ this.text=t; };
"""
def failing_tts(code):
    return """
window.__spoken = [];
Object.defineProperty(window, 'speechSynthesis', {value: {
  speaking:false, getVoices(){ return [{lang:'en-US', name:'Net voice', localService:false}]; }, cancel(){},
  speak(u){ window.__spoken.push({text:u.text}); setTimeout(()=>u.onerror&&u.onerror({error:'%s'}), 20); }
}});
window.SpeechSynthesisUtterance = function(t){ this.text=t; };
""" % code
SILENT_TTS = """
window.__spoken = [];
Object.defineProperty(window, 'speechSynthesis', {value: {
  speaking:false, getVoices(){ return [{lang:'en-US', name:'E', localService:true}]; }, cancel(){},
  speak(u){ window.__spoken.push({text:u.text}); }
}});
window.SpeechSynthesisUtterance = function(t){ this.text=t; };
"""
NO_TTS = "delete window.speechSynthesis; delete window.SpeechSynthesisUtterance;"
CODES = re.compile(r"not-allowed|synthesis-failed|\bnetwork\b|interrupted|audio-busy|\(\w+-\w+\)")
STATUS_JS = "document.querySelector('[data-listen-status]').textContent"


def home(browser, *scripts, **ctx):
    context = browser.new_context(**ctx)
    for sc in scripts:
        context.add_init_script(sc)
    page = context.new_page()
    page.goto(BASE + "index.html")
    expect(page.locator("[data-listen]")).to_be_visible()
    return page


def spoken(page):
    return " ".join(page.evaluate("window.__spoken.map(s => s.text)"))


def test_navigation_is_compact(browser):
    page = home(browser, NO_SPEECH)
    labels = [a.inner_text() for a in page.locator("#site-nav a").all()]
    assert labels == (["Experience", "Projects", "Architecture", "Résumé"] if HAS_RESUME
                      else ["Experience", "Projects", "Architecture"])


def test_buttons_have_visible_focus(browser):
    page = home(browser, NO_SPEECH)
    page.focus(".cta-primary .btn")
    shadow = page.evaluate("getComputedStyle(document.activeElement).boxShadow")
    page.keyboard.press("Tab")
    assert shadow and shadow != "none"


def test_featured_projects_right_after_hero(browser):
    page = home(browser, NO_SPEECH)
    assert page.evaluate("document.querySelector('.hero').nextElementSibling.id") == "projects"
    leads = page.locator("[data-lead]")
    assert [leads.nth(i).get_attribute("data-lead") for i in range(2)] == SLUGS[:2]
    for i, slug in enumerate(SLUGS[:2]):
        card = leads.nth(i)
        assert [d.inner_text().split("\n")[0].strip() for d in card.locator("dt").all()][:2] == ["PROBLEM", "WHAT I BUILT"] or \
               [d.text_content().strip() for d in card.locator("dt").all()][:2] == ["Problem", "What I built"]
        expect(card.locator("dt").nth(2)).to_contain_text("Verified result")
        assert card.locator(".scope-badge").count() >= 1
        expect(card.locator("a", has_text="Case study")).to_have_attribute("href", f"./projects/{slug}.html")
        expect(card.locator("a", has_text="Recorded demo")).to_have_attribute("href", f"./projects/{slug}.html#walkthrough")
        expect(card.locator("a", has_text="Interactive walkthrough")).to_have_attribute("href", f"./demos/{slug}.html")
    for slug in SLUGS[2:]:
        row = page.locator(f".project-list li:has(a[href='./projects/{slug}.html'])")
        expect(row).to_have_count(1)
        expect(row.locator(".scope-badge").first).to_be_visible()
    # no lab claims Azure validation
    assert page.locator("#projects .project-feature .s-azure, #projects .project-list .s-azure").count() == 0


def test_architecture_tabs_and_diagrams(browser):
    page = home(browser, NO_SPEECH)
    expect(page.locator("[data-tab=delivery]")).to_have_attribute("aria-selected", "true")
    expect(page.locator("#arch-delivery")).to_be_visible()
    expect(page.locator("#arch-infrastructure")).to_be_hidden()
    expect(page.locator("#arch-delivery .arch-wide")).to_contain_text("Approval gate")
    expect(page.locator("#arch-delivery .arch-wide")).to_contain_text("Rollback path")
    assert page.evaluate("[...document.querySelectorAll('#arch-delivery .arch-wide text')].filter(t => t.textContent === 'Smoke test').length") == 3
    for key in ("delivery", "infrastructure", "reliability"):
        page.click(f"[data-tab={key}]")
        panel = page.locator(f"#arch-{key}")
        expect(panel).to_be_visible()
        expect(panel.locator("figcaption")).to_contain_text("Portfolio lab")
        svg = panel.locator(".arch-wide svg.arch-svg")
        assert svg.get_attribute("role") == "img"
        assert page.evaluate(f"document.querySelector('#arch-{key} .arch-wide svg').getBBox().width") > 700
        ids = page.evaluate(f"[...document.querySelectorAll('#arch-{key} .arch-wide [marker-end]')].map(e => e.getAttribute('marker-end'))")
        assert ids and all(i.startswith(f"url(#{key}-") for i in ids)
    page.focus("[data-tab=reliability]")
    page.keyboard.press("ArrowRight")
    expect(page.locator("[data-tab=delivery]")).to_be_focused()
    expect(page.locator("#arch-delivery")).to_be_visible()
    page.goto(BASE + "index.html#arch-reliability")
    expect(page.locator("#arch-reliability")).to_be_visible()
    expect(page.locator("[data-tab=reliability]")).to_have_attribute("aria-selected", "true")


def test_case_studies_and_walkthroughs(browser):
    page = home(browser, NO_SPEECH)
    for slug in SLUGS:
        page.goto(BASE + f"projects/{slug}.html")
        for sid in ("problem", "environment", "architecture", "implementation", "decisions", "failure", "recovery",
                    "result", "walkthrough", "evidence"):
            expect(page.locator(f"section#{sid}")).to_have_count(1)
        labels = {b.inner_text() for b in page.locator(".scope .scope-badge").all()}
        assert labels and labels <= {"LOCAL", "SIMULATED", "CI-VALIDATED", "NEEDS AZURE (NOT YET RUN)", "AZURE-VALIDATED"}, labels
        expect(page.locator("#walkthrough h3", has_text="Recorded demo")).to_be_visible()
        expect(page.locator("#walkthrough video source")).to_have_attribute("src", f"../assets/video/{slug}.mp4")
        expect(page.locator("#walkthrough a", has_text="interactive walkthrough")).to_have_attribute("href", f"../demos/{slug}.html")
        assert page.locator(".diagram img").count() >= 1
        page.goto(BASE + f"demos/{slug}.html")
        expect(page.locator("h1")).to_contain_text("Interactive walkthrough")
        expect(page.locator(".count")).to_have_text(re.compile("Scene 1 of"))


def test_mobile_layout(browser):
    page = home(browser, NO_SPEECH, viewport={"width": 390, "height": 844})
    for btn in page.locator(".hero .cta .btn").all():
        b = btn.bounding_box()
        assert b["height"] >= 42 and b["x"] >= 0 and b["x"] + b["width"] <= 390, btn.inner_text()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.click(".menu-toggle")
    for a in page.locator("#site-nav a").all():
        assert a.bounding_box()["height"] >= 44
    for card in page.locator(".project-feature .row-actions .btn").all():
        assert card.bounding_box()["height"] >= 40
    for url in ("projects/aks-observability-sre-lab.html", "demos/aks-delivery-platform.html"):
        page.goto(BASE + url)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), url
    if HAS_RESUME:
        page.goto(BASE + "resume.html")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_resume_page(browser):
    if not HAS_RESUME:
        pytest.skip("resume not published")
    page = home(browser, NO_SPEECH)
    page.click(".cta [data-cta=resume]")
    expect(page).to_have_url(re.compile(r"resume\.html$"))
    expect(page.locator("#site-nav a[aria-current=page]")).to_have_text("Résumé")
    # A readable HTML résumé: no PDF viewer, no downloads, no PDF or Word file on the site.
    assert page.locator("iframe, embed, object").count() == 0
    assert page.locator("a[download], a[href$='.pdf'], a[href$='.docx'], a[href$='.doc']").count() == 0
    assert "download" not in page.locator("main").inner_text().lower()
    assert not [f for f in SITE.rglob("*") if f.suffix.lower() in (".pdf", ".doc", ".docx")]
    expect(page.locator("#resume-name")).to_have_text("Srinivasa Rao Gollapudi")
    heads = [h.inner_text() for h in page.locator(".resume-role-head h3").all()]
    assert heads == ["Senior DevOps Engineer", "DevOps Engineer", "Technical Lead",
                     "Senior System Administrator (Cloud Infrastructure)"], heads
    assert "+91" not in page.locator("main").inner_text()          # phone number stays off the public site
    m = browser.new_page(viewport={"width": 390, "height": 844})
    m.goto(BASE + "resume.html")
    expect(m.locator(".resume-role").first).to_be_visible()
    assert m.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_phone_diagrams_are_readable(browser):
    page = home(browser, NO_SPEECH, viewport={"width": 390, "height": 844})
    for key in ("delivery", "infrastructure", "reliability"):
        page.click(f"[data-tab={key}]")
        narrow = page.locator(f"#arch-{key} .arch-narrow svg")
        expect(narrow).to_be_visible()
        expect(page.locator(f"#arch-{key} .arch-wide")).to_be_hidden()
        box = narrow.bounding_box()
        vb_w = float(narrow.get_attribute("viewBox").split()[2])
        assert box["width"] / vb_w >= 0.85, (key, box["width"])     # 12.5px labels render at 10.6px or larger
        assert box["x"] >= 0 and box["x"] + box["width"] <= 390
        ids = page.evaluate(f"[...document.querySelectorAll('#arch-{key} .arch-narrow [marker-end]')].map(e => e.getAttribute('marker-end'))")
        assert ids and all(i.startswith(f"url(#{key}-m-") for i in ids)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


# ---------------- Listen to Portfolio ----------------
NARRATION_START = "This is the portfolio of Srinivasa Rao Gollapudi, a Senior Azure DevOps Engineer and Site Reliability Engineer with more than 11 years in IT."
# Like HOLD_TTS, and records whether a second utterance was ever queued while one was still playing.
OVERLAP_TTS = HOLD_TTS.replace("speak(u){", "speak(u){ if (this._u) window.__overlap = true;")
NO_MIC = """
window.__mic = 0;
if (navigator.mediaDevices) navigator.mediaDevices.getUserMedia = () => { window.__mic++; return Promise.reject(new Error('no')); };
"""
LISTEN = "[data-listen]"


def label(page):
    return page.locator("[data-listen-label]").inner_text()


def narration(page):
    return page.locator("[data-listen-text]").text_content().strip()


def test_hero_actions_and_outcomes(browser):
    page = home(browser, NO_SPEECH)
    hero = page.locator(".hero")
    expect(hero.locator(".headline")).to_have_text("Senior Azure DevOps Engineer | Site Reliability Engineer (SRE)")
    for fact in ("11+ years in IT", "Immediate joiner", "Remote only", "Bangalore, India"):
        expect(hero.locator(".facts")).to_contain_text(fact)
    buttons = [" ".join(b.inner_text().split()) for b in hero.locator(".cta .btn").all()]
    assert buttons == (["View Projects", "View Résumé", "🔊 Listen to Portfolio"] if HAS_RESUME
                       else ["View Projects", "🔊 Listen to Portfolio"]), buttons
    # The old intro and tour controls are gone.
    for gone in ("[data-intro-play]", "[data-tour-start]", "[data-intro-transcript]", "[data-intro]", "[data-tour]",
                 ".cta-secondary", "text=Play intro", "text=Start Portfolio Tour", "text=Intro transcript"):
        assert page.locator(gone).count() == 0, gone
    expect(page.locator("[data-listen-fallback]")).to_be_hidden()
    assert "Senior Azure DevOps Engineer" not in hero.locator(".lead").inner_text()
    assert page.locator("text=Download Resume").count() == 0
    card = page.locator(".outcomes.latest")
    expect(card.locator(".outcomes-label")).to_have_text("Latest Role")
    expect(card.locator(".latest-role")).to_have_text("Pulse Data Labs · Senior DevOps Engineer · Client: URUS · Feb 2026–Sep 2026")
    pts = card.locator(".latest-points").inner_text()
    for t in ("AKS deployments", "reusable Terraform modules", "L3 escalations"):
        assert t in pts, t
    # Teknip's results are not on the hero card; they sit with Teknip in the timeline.
    for t in ("Teknip", "MITIE", "10+", "45%", "Days"):
        assert t not in card.inner_text(), t
    teknip = page.locator(".timeline > li").nth(1)
    res = teknip.locator(".role-results")
    for t in ("10+ applications deployed to AKS", "Days → hours release lead time", "~45% fewer false-positive alerts"):
        expect(res).to_contain_text(t)
    # Mobile: the card stacks below the intro and buttons.
    m = home(browser, NO_SPEECH, viewport={"width": 390, "height": 844})
    assert m.locator(".outcomes.latest").bounding_box()["y"] > m.locator(".hero .cta").bounding_box()["y"]


def test_names_dates_and_attribution_consistent(browser):
    page = home(browser, NO_SPEECH)
    roles = page.locator(".timeline > li")
    expect(roles.nth(0).locator("h3")).to_have_text("Senior DevOps Engineer")
    expect(roles.nth(0).locator(".dates")).to_have_text("Feb 2026–Sep 2026")
    expect(roles.nth(0).locator(".org")).to_have_text("Pulse Data Labs · Client: URUS")
    expect(roles.nth(1).locator(".dates")).to_have_text("May 2024–Feb 2026")
    expect(roles.nth(1).locator(".org")).to_have_text("Teknip Technology Pvt Ltd · Client: MITIE")
    teknip, pulse = roles.nth(1).inner_text(), roles.nth(0).inner_text()
    assert "10+ applications" in teknip and "days to hours" in teknip and "~45%" in teknip
    assert "10+" not in pulse and "45%" not in pulse and "days to hours" not in pulse
    assert roles.nth(1).locator(".role-results li").count() == 3
    text = narration(page)
    assert text.startswith(NARRATION_START)
    for t in ("Pulse Data Labs", "URUS", "February to September 2026", "AKS Delivery Platform lab", "smoke test",
              "rolled back", "AKS Observability and SRE Incident Lab", "burn-rate alert", "traces", "simulated",
              "run locally", "View Projects", "View Résumé"):
        assert t in text, t
    # Teknip's results are not credited to Pulse Data Labs in the narration.
    for t in ("Teknip", "45", "10+", "days to hours"):
        assert t not in text, t
    assert 115 <= len(text.split()) <= 150   # measured ~60 s for 164 words in Chrome; this keeps it within 45–60 s
    if HAS_RESUME:
        page.goto(BASE + "resume.html")
        rs = page.locator(".resume-role")
        expect(rs.nth(0).locator(".dates")).to_have_text("Feb 2026–Sep 2026")
        expect(rs.nth(0).locator(".resume-sub")).to_have_text("Pulse Data Labs | Bangalore, India | Client: URUS")
        expect(rs.nth(1).locator(".dates")).to_have_text("May 2024–Feb 2026")
        expect(rs.nth(1).locator(".resume-sub")).to_have_text("Teknip Technology Pvt Ltd | Bangalore, India | Client: MITIE")


def test_listen_nothing_plays_until_clicked(browser):
    page = home(browser, "window.__srMode='speak';" + FAKE_SR, NO_MIC, HOLD_TTS)
    page.mouse.click(5, 300)          # a click elsewhere does not start audio
    page.keyboard.press("Tab")
    page.wait_for_timeout(600)
    assert page.evaluate("window.__spoken.length") == 0
    page.click(LISTEN)
    page.wait_for_function("window.__spoken.length > 0")
    assert page.evaluate("window.__rec.length") == 0 and page.evaluate("window.__mic") == 0
    assert page.evaluate("window.scrollY") == 0          # no guided scrolling


def test_listen_start_and_stop(browser):
    page = home(browser, HOLD_TTS)
    btn = page.locator(LISTEN)
    btn.click()
    expect(page.locator("[data-listen-label]")).to_have_text("Stop Audio")
    page.wait_for_function("window.speechSynthesis.speaking")
    assert page.evaluate("window.__spoken[0].text").startswith("This is the portfolio of Srinivasa Rao Gollapudi")
    btn.click()
    expect(page.locator("[data-listen-label]")).to_have_text("Listen to Portfolio")
    expect(page.locator("[data-listen-status]")).to_have_text("Audio stopped.")
    assert page.evaluate("window.speechSynthesis.speaking") is False
    page.wait_for_timeout(400)
    assert label(page) == "Listen to Portfolio"     # a late callback does not flip the label back


def test_listen_replays_from_beginning(browser):
    page = home(browser, FAKE_TTS)
    page.click(LISTEN)
    page.wait_for_function("window.__spoken.length >= 3")
    page.click(LISTEN)                                 # stop part-way
    expect(page.locator("[data-listen-label]")).to_have_text("Listen to Portfolio")
    n = page.evaluate("window.__spoken.length")
    page.click(LISTEN)                                 # play again
    page.wait_for_function(f"window.__spoken.length > {n}")
    assert page.evaluate(f"window.__spoken[{n}].text").startswith(NARRATION_START[:40])


def test_listen_natural_completion(browser):
    page = home(browser, FAKE_TTS)
    page.click(LISTEN)
    expect(page.locator("[data-listen-label]")).to_have_text("Stop Audio")
    expect(page.locator("[data-listen-label]")).to_have_text("Listen to Portfolio", timeout=10000)
    expect(page.locator("[data-listen-status]")).to_have_text("Walkthrough finished.")
    spoken = " ".join(page.evaluate("window.__spoken.map(s => s.text)"))
    assert spoken == narration(page)
    assert all(l.startswith("en") for l in page.evaluate("window.__spoken.map(s => s.lang)"))


def test_listen_rapid_clicks_never_overlap(browser):
    page = home(browser, OVERLAP_TTS)
    btn = page.locator(LISTEN)
    for _ in range(7):
        btn.click(delay=0)
    expect(page.locator("[data-listen-label]")).to_have_text("Stop Audio")      # odd number of clicks: playing
    page.wait_for_function("window.speechSynthesis.speaking")
    page.wait_for_timeout(500)
    assert not page.evaluate("window.__overlap")
    assert page.evaluate("window.__spoken[window.__spoken.length - 1].text").startswith(NARRATION_START[:40])
    btn.click()
    expect(page.locator("[data-listen-label]")).to_have_text("Listen to Portfolio")
    page.wait_for_timeout(500)
    assert page.evaluate("window.speechSynthesis.speaking") is False


@pytest.mark.parametrize("script,message", [
    (NO_TTS, "Audio isn't available in this browser."),
    (failing_tts("synthesis-failed"), "Audio couldn't play."),
    (failing_tts("not-allowed"), "Your browser blocked audio."),
])
def test_listen_fallback_shows_text(browser, script, message):
    page = home(browser, script)
    page.click(LISTEN)
    expect(page.locator("[data-listen-status]")).to_contain_text(message, timeout=15000)
    expect(page.locator("[data-listen-status]")).to_contain_text("Here is the narration as text.")
    fb = page.locator("[data-listen-fallback]")
    expect(fb).to_be_visible()
    assert fb.locator("button, audio, [data-listen]").count() == 0        # no second audio control
    assert fb.inner_text().find(NARRATION_START) >= 0
    expect(page.locator("[data-listen-label]")).to_have_text("Listen to Portfolio")
    assert page.locator(".hero button").count() == 1
    assert not CODES.search(page.evaluate(STATUS_JS))


def test_listen_silent_speech_falls_back(browser):
    page = home(browser, SILENT_TTS)
    page.click(LISTEN)
    expect(page.locator("[data-listen-status]")).to_contain_text("Audio couldn't play.", timeout=20000)
    expect(page.locator("[data-listen-fallback]")).to_be_visible()
    expect(page.locator("[data-listen-label]")).to_have_text("Listen to Portfolio")


def test_listen_keyboard(browser):
    page = home(browser, HOLD_TTS)
    page.focus("[data-cta='projects']")
    page.keyboard.press("Tab")
    if HAS_RESUME:
        page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.matches('[data-listen]')")
    shadow = page.evaluate("getComputedStyle(document.activeElement).boxShadow")
    assert shadow and shadow != "none"                          # visible focus ring
    page.keyboard.press("Enter")
    expect(page.locator("[data-listen-label]")).to_have_text("Stop Audio")
    page.keyboard.press("Space")
    expect(page.locator("[data-listen-label]")).to_have_text("Listen to Portfolio")
    page.keyboard.press("Space")
    expect(page.locator("[data-listen-label]")).to_have_text("Stop Audio")
    page.keyboard.press("Escape")
    expect(page.locator("[data-listen-label]")).to_have_text("Listen to Portfolio")
    assert page.evaluate("window.speechSynthesis.speaking") is False


def test_listen_stops_when_leaving_page(browser):
    page = home(browser, HOLD_TTS)
    page.click(LISTEN)
    page.wait_for_function("window.speechSynthesis.speaking")
    page.evaluate("window.dispatchEvent(new PageTransitionEvent('pagehide'))")
    assert page.evaluate("window.speechSynthesis.speaking") is False


@pytest.mark.parametrize("width", [320, 375, 414, 768])
def test_hero_actions_fit_on_mobile(browser, width):
    page = home(browser, NO_SPEECH, viewport={"width": width, "height": 800})
    boxes = [b.bounding_box() for b in page.locator(".hero .cta .btn").all()]
    for b in boxes:
        assert b["x"] >= 0 and b["x"] + b["width"] <= width and b["height"] >= 42
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    lb = page.locator(LISTEN)
    assert lb.evaluate("el => el.scrollWidth <= el.clientWidth")        # label not clipped


def test_hero_links_reach_projects_and_resume(browser):
    page = home(browser, NO_SPEECH)
    page.click("[data-cta='projects']")
    page.wait_for_function("location.hash === '#projects'")
    expect(page.locator("#projects")).to_be_in_viewport()
    if HAS_RESUME:
        page.goto(BASE + "index.html")
        with page.expect_navigation():
            page.click("[data-cta='resume']")
        assert page.url.endswith("resume.html")
        expect(page.locator("#resume-name")).to_have_text("Srinivasa Rao Gollapudi")
    for slug in ("aks-delivery-platform", "aks-observability-sre-lab"):
        assert page.goto(BASE + f"projects/{slug}.html").ok
        assert page.goto(BASE + f"demos/{slug}.html").ok


# ---------------- one-link portfolio: source pages, no outside links ----------------
def test_no_github_links_in_public_pages():
    bad = []
    for f in SITE.rglob("*.html"):
        for ref in re.findall(r'href="([^"]+)"', f.read_text(encoding="utf-8")):
            if "github.com" in ref and "github.io" not in ref:
                bad.append(f"{f.relative_to(SITE)} -> {ref}")
    assert not bad, bad[:10]


def test_source_pages(browser):
    page = browser.new_page()
    page.goto(BASE + "source/index.html")
    expect(page.locator(".src-list li")).to_have_count(6)
    page.click("text=AKS Delivery Platform with Azure DevOps")
    expect(page.locator(".md h2").first).to_contain_text("AKS Delivery Platform")
    expect(page.locator("h1")).to_have_count(1)
    page.click(".src-tree summary:text('scripts')")
    page.click(".src-tree a:text('deploy_with_rollback.sh')")
    expect(page).to_have_url(re.compile(r"source/aks-delivery-platform/scripts/deploy_with_rollback\.sh\.html$"))
    expect(page.locator(".src-code")).to_contain_text("helm rollback")
    expect(page.locator(".src-license")).to_contain_text("MIT License")
    page.goto(BASE + "source/LICENSE.html")
    expect(page.locator(".license-text")).to_contain_text("Permission is hereby granted")
    # Case study and walkthrough link to the on-site source
    page.goto(BASE + "projects/aks-observability-sre-lab.html")
    page.click(".case-links >> text=Browse the source")
    expect(page.locator("h1")).to_have_text("AKS Observability and SRE Incident Lab")
    page.goto(BASE + "source/aks-observability-sre-lab/docs/postmortem.md.html")
    expect(page.locator(".md")).to_contain_text("Postmortem")
    # every tracked project file has a page, and nothing secret-looking is published
    import subprocess
    root = SITE.parent
    files = subprocess.run(["git", "-C", str(root), "ls-files", "projects"], capture_output=True, text=True).stdout.split()
    for f in files:
        parts = f.split("/")
        slug = {"01-aks-delivery-platform": "aks-delivery-platform", "03-aks-observability-sre-lab": "aks-observability-sre-lab"}.get(parts[1])
        if slug:
            assert (SITE / "source" / slug / ("/".join(parts[2:]) + ".html")).exists(), f
    assert not [p for p in (SITE / "source").rglob("*") if re.search(r"\.(pem|key|tfstate)|local\.settings\.json\.html$", p.name)]


def test_featured_lab_screenshots(browser):
    page = home(browser, NO_SPEECH)
    for slug, scope in (("aks-delivery-platform", ["Local"]), ("aks-observability-sre-lab", ["Local", "Simulated"])):
        card = page.locator(f"[data-lead='{slug}']")
        img = card.locator(".lab-shot img")
        img.scroll_into_view_if_needed()
        assert img.evaluate("el => el.complete && el.naturalWidth > 1000")
        assert len(img.get_attribute("alt")) > 60
        assert card.locator(".lab-shot a").get_attribute("href").endswith(f"projects/{slug}.html")
        badges = [b.inner_text().strip().title() for b in card.locator(".lab-shot .scope-badge").all()]
        assert badges == scope, badges
        for b in card.locator(".lab-shot .scope-badge").all():
            assert b.is_visible()
