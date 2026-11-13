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


# ---------------- portfolio redesign: tour, architecture, case studies ----------------
WELCOME = ("Welcome to Srinivasa\u2019s portfolio. Explore his Azure DevOps and SRE experience, view his resume, "
           "take a short tour of the project architectures, or ask the portfolio a question. "
           "He is open to fully remote Azure DevOps, SRE and Azure Infrastructure Engineer roles only.")
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
STATUS_JS = "[...document.querySelectorAll('[data-tour-note],[data-welcome-status],.status-text')].map(e => e.textContent).join(' ')"


def home(browser, *scripts, **ctx):
    context = browser.new_context(**ctx)
    for sc in scripts:
        context.add_init_script(sc)
    page = context.new_page()
    page.goto(BASE + "index.html")
    expect(page.locator("[data-intro-play]")).to_be_visible()
    return page


def spoken(page):
    return " ".join(page.evaluate("window.__spoken.map(s => s.text)"))


def test_navigation_is_compact(browser):
    page = home(browser, NO_SPEECH)
    labels = [a.inner_text() for a in page.locator("#site-nav a").all()]
    assert labels == (["Experience", "Projects", "Architecture", "Resume", "Contact", "Ask the Portfolio"] if HAS_RESUME
                      else ["Experience", "Projects", "Architecture", "Contact", "Ask the Portfolio"])


def test_hero_actions_and_outcomes(browser):
    page = home(browser, NO_SPEECH)
    hero = page.locator(".hero")
    expect(hero.locator(".headline")).to_have_text("Senior Azure DevOps Engineer | Site Reliability Engineer (SRE) | Azure Infrastructure Engineer")
    for fact in ("11+ years in IT", "Immediate joiner", "Fully remote only", "Bangalore, India"):
        expect(hero.locator(".facts")).to_contain_text(fact)
    primaries = [b.inner_text() for b in hero.locator(".cta-primary .btn.primary").all()]
    assert primaries == (["View Projects", "View Resume"] if HAS_RESUME else ["View Projects"])
    secondary = [b.inner_text() for b in hero.locator(".cta-secondary .btn").all()]
    assert secondary[:2] == ["▶ Play intro", "Start Portfolio Tour"], secondary
    assert hero.locator(".cta-secondary .btn.primary").count() == 0
    assert page.locator("[data-tour-start]").count() == 1
    assert "Senior Azure DevOps Engineer" not in hero.locator(".lead").inner_text()
    # the resume is view-only: no download links anywhere on the home page
    assert page.locator("a[download], [data-resume-download]").count() == 0
    assert page.locator("a[href*='linkedin']").count() == 0
    out = page.locator(".outcomes")
    expect(out).to_contain_text("Professional experience")
    # The card shows the most recent (previous) employer from the resume: Pulse Data Labs, client URUS.
    expect(out).to_contain_text("Pulse Data Labs (client: URUS), Feb 2026 – Sep 2026")
    assert "Teknip" not in out.inner_text() and "MITIE client" not in out.inner_text()
    for t in ("L3 escalation in a 24x7 PagerDuty on-call rotation", "Defined SLIs, SLOs and error budgets with application teams"):
        expect(out).to_contain_text(t)
    # No figures are attributed to Pulse Data Labs: the resume has none for that role.
    for metric in ("10+", "45%", "Days → hours"):
        assert metric not in out.inner_text()
    # Remote-only preference is visible in the hero and in the contact section, worded the same.
    pref = "Open to fully remote Senior Azure DevOps Engineer, Site Reliability Engineer (SRE) and Azure Infrastructure Engineer roles only."
    expect(hero.locator("[data-remote-pref]")).to_have_text(pref)
    expect(page.locator("#contact [data-remote-pref]")).to_have_text(pref)
    # Experience section lists Pulse Data Labs first, with the MITIE metrics staying on Teknip Technology.
    orgs = [o.inner_text() for o in page.locator(".timeline .org").all()]
    assert orgs[0] == "Pulse Data Labs · Client: URUS", orgs
    assert orgs[1].startswith("Teknip Technology"), orgs


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


def test_nothing_plays_until_play_intro(browser):
    page = home(browser, FAKE_SR, FAKE_TTS)
    page.wait_for_timeout(400)
    page.click("h1")
    page.keyboard.press("Space")
    page.wait_for_timeout(400)
    assert page.evaluate("window.__spoken.length") == 0
    expect(page.locator("[data-intro]")).to_be_hidden()
    page.click("[data-intro-transcript]")                       # transcript without audio
    expect(page.locator("[data-intro-text]")).to_have_text(WELCOME)
    assert page.evaluate("window.__spoken.length") == 0
    page.click("[data-intro-play]")
    page.wait_for_function("window.__spoken.length > 0")
    page.wait_for_timeout(300)
    assert spoken(page) == WELCOME
    assert page.evaluate("window.__rec.length") == 0


def test_intro_play_pause_resume_stop(browser):
    page = home(browser, FAKE_SR, HOLD_TTS)
    page.click("[data-intro-play]")
    toggle = page.locator("[data-intro-toggle]")
    expect(toggle).to_have_text("Pause")
    expect(page.locator("[data-intro-status]")).to_contain_text("Playing")
    toggle.click()
    expect(toggle).to_have_text("Resume")
    assert page.evaluate("window.speechSynthesis.speaking") is False
    toggle.click()
    expect(toggle).to_have_text("Pause")
    page.wait_for_function("window.speechSynthesis.speaking")
    page.click("[data-intro-stop]")
    expect(toggle).to_have_text("Play")
    expect(page.locator("[data-intro-status]")).to_contain_text("stopped")
    assert page.evaluate("window.speechSynthesis.speaking") is False
    expect(page.locator("[data-intro-stop]")).to_be_disabled()
    assert page.evaluate("window.__rec.length") == 0


def test_pause_stops_and_resume_repeats_sentence(browser):
    """Pause must not rely on speechSynthesis.pause(): Chrome on Windows hangs the next sentence."""
    page = home(browser, HOLD_TTS)
    page.click("[data-intro-play]")
    page.wait_for_function("window.speechSynthesis._u && window.speechSynthesis._u.text.startsWith('Welcome')")
    page.click("[data-intro-toggle]")                       # Pause
    assert page.evaluate("window.speechSynthesis.speaking") is False
    assert page.evaluate("window.__paused || 0") == 0       # engine pause() is never used
    page.wait_for_timeout(400)
    assert page.evaluate("window.__spoken.length") == 1     # nothing new while paused
    page.click("[data-intro-toggle]")                       # Resume
    page.wait_for_function("window.__spoken.length === 2")
    assert page.evaluate("window.__spoken[1].text").startswith("Welcome")   # repeats the paused sentence
    page.evaluate("window.speechSynthesis._u.onend()")      # finish it: next sentence follows
    page.wait_for_function("window.__spoken.length === 3")
    assert page.evaluate("window.__spoken[2].text").startswith("Explore")


def test_tour_controls_and_captions(browser):
    page = home(browser, FAKE_SR, HOLD_TTS)
    page.click("[data-tour-start]")
    bar = page.locator("[data-tour]")
    expect(bar).to_be_visible()
    expect(bar.locator("[data-tour-step]")).to_have_text("Delivery · 1 of 4")
    expect(bar.locator("[data-tour-caption]")).to_contain_text("Delivery.")
    expect(page.locator("#arch-delivery")).to_have_class(re.compile("tour-focus"))
    page.wait_for_timeout(300)
    assert page.evaluate("window.__spoken.length") == 0
    play = page.locator("[data-tour-play]")
    play.click()
    page.wait_for_function("window.speechSynthesis._u && window.speechSynthesis._u.text.startsWith('Delivery.')")
    expect(play).to_have_text("Pause narration")
    play.click()
    expect(play).to_have_text("Resume narration")
    assert page.evaluate("window.speechSynthesis.speaking") is False
    play.click()
    expect(play).to_have_text("Pause narration")
    page.wait_for_function("window.speechSynthesis.speaking")
    page.click("[data-tour-next]")
    expect(bar.locator("[data-tour-step]")).to_have_text("Infrastructure · 2 of 4")
    expect(bar.locator("[data-tour-caption]")).to_contain_text("Infrastructure.")
    expect(page.locator("[data-tab=infrastructure]")).to_have_attribute("aria-selected", "true")
    page.wait_for_function("window.speechSynthesis._u && window.speechSynthesis._u.text.startsWith('Infrastructure')")
    assert page.evaluate("window.__cancelled") >= 1
    page.click("[data-tour-back]")
    page.wait_for_function("window.speechSynthesis._u && window.speechSynthesis._u.text.startsWith('Delivery.')")
    page.click("[data-tour] [data-mute]")
    assert page.evaluate("window.speechSynthesis.speaking") is False
    expect(bar.locator("[data-tour-caption]")).to_contain_text("Delivery.")
    n = page.evaluate("window.__spoken.length")
    page.click("[data-tour-next]")
    page.wait_for_timeout(400)
    assert page.evaluate("window.__spoken.length") == n
    play.click()
    page.wait_for_function(f"window.__spoken.length > {n}")
    expect(page.locator("[data-tour] [data-mute]")).to_have_attribute("aria-pressed", "false")
    page.click("[data-tour-stop]")
    expect(bar).to_be_hidden()
    assert page.evaluate("window.speechSynthesis.speaking") is False
    assert page.evaluate("window.__rec.length") == 0


def test_intro_and_tour_never_overlap(browser):
    page = home(browser, HOLD_TTS)
    page.click("[data-intro-play]")
    page.wait_for_function("window.speechSynthesis.speaking")
    page.click("[data-tour-start]")
    assert page.evaluate("window.speechSynthesis.speaking") is False   # intro stopped by the tour
    page.click("[data-tour-play]")
    page.wait_for_function("window.speechSynthesis._u && window.speechSynthesis._u.text.startsWith('Delivery.')")
    page.click("[data-tour-stop]")
    page.click("[data-intro-play]")
    page.wait_for_function("window.speechSynthesis._u && window.speechSynthesis._u.text.startsWith('Welcome')")


def test_tour_finish_and_free_exploration(browser):
    page = home(browser, NO_SPEECH, FAKE_TTS)
    page.click("[data-tour-start]")
    for _ in range(3):
        page.click("[data-tour-next]")
    expect(page.locator("[data-tour-next]")).to_have_text("Finish")
    expect(page.locator("#projects")).to_have_class(re.compile("tour-focus"))
    page.locator("#projects a", has_text="Case study").first.click()
    expect(page).to_have_url(re.compile(r"projects/aks-delivery-platform\.html$"))


def test_speech_failure_shows_friendly_fallback(browser):
    page = home(browser, failing_tts("synthesis-failed"))
    page.click("[data-tour-start]")
    page.click("[data-tour-play]")
    note = page.locator("[data-tour-note]")
    expect(note).to_contain_text("Audio couldn't start")
    expect(page.locator("[data-tour-play]")).to_have_text("Try audio again")
    expect(page.locator("[data-tour-caption]")).to_contain_text("Delivery.")
    assert page.evaluate("window.__spoken.length") == 2
    page.click("[data-tour-play]")
    expect(note).to_contain_text("Audio couldn't start")
    page.click("[data-tour-stop]")
    page.click("[data-intro-play]")
    expect(page.locator("[data-intro-status]")).to_contain_text("Audio couldn't start")
    expect(page.locator("[data-intro-text]")).to_be_visible()
    expect(page.locator("[data-intro-toggle]")).to_have_text("Try again")
    assert not CODES.search(page.evaluate("[...document.querySelectorAll('[data-tour-note],[data-intro-status],.status-text')].map(e => e.textContent).join(' ')"))


def test_blocked_and_silent_speech(browser):
    page = home(browser, failing_tts("not-allowed"))
    page.click("[data-intro-play]")
    expect(page.locator("[data-intro-status]")).to_contain_text("needs a click")
    page = home(browser, SILENT_TTS)
    page.click("[data-intro-play]")
    expect(page.locator("[data-intro-status]")).to_contain_text("Audio couldn't start", timeout=20000)


def test_no_speech_support_keeps_text(browser):
    page = home(browser, NO_TTS)
    expect(page.locator("[data-intro-play]")).to_be_disabled()
    page.click("[data-intro-transcript]")
    expect(page.locator("[data-intro-text]")).to_have_text(WELCOME)
    page.click("[data-tour-start]")
    expect(page.locator("[data-tour-play]")).to_be_disabled()
    expect(page.locator("[data-tour-caption]")).to_contain_text("Delivery.")
    page.click("[data-tour-next]")
    expect(page.locator("[data-tour-caption]")).to_contain_text("Infrastructure.")


def test_speech_stops_when_leaving_page(browser):
    page = home(browser, HOLD_TTS)
    page.click("[data-tour-start]")
    page.click("[data-tour-play]")
    page.wait_for_function("window.speechSynthesis.speaking")
    page.evaluate("window.dispatchEvent(new PageTransitionEvent('pagehide'))")
    assert page.evaluate("window.speechSynthesis.speaking") is False


def test_tour_keyboard(browser):
    page = home(browser, NO_SPEECH, FAKE_TTS)
    page.locator("[data-tour-start]").focus()
    page.keyboard.press("Enter")
    expect(page.locator("[data-tour-next]")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("[data-tour-step]")).to_contain_text("2 of 4")
    page.keyboard.press("Escape")
    expect(page.locator("[data-tour]")).to_be_hidden()


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
    expect(page.locator("#site-nav a[aria-current=page]")).to_have_text("Resume")
    # view-only: page images, no PDF frame, no download link, no DOCX/PDF published
    assert page.locator("iframe, embed, object").count() == 0
    imgs = page.locator(".pdf-pages img")
    expect(imgs).to_have_count(3)
    expect(imgs.first).to_be_visible()
    assert page.locator("a[download]").count() == 0
    assert not list(SITE.glob("assets/resume/*.docx")) and not list(SITE.glob("assets/resume/*.pdf"))
    heads = [h.text_content() for h in page.locator("article.sr-only h3").all()]
    assert heads[0].startswith("Senior DevOps Engineer") and len(heads) == 4
    # phones: the same page images
    m = browser.new_page(viewport={"width": 390, "height": 844})
    m.goto(BASE + "resume.html")
    expect(m.locator(".pdf-pages img").first).to_be_visible()
    m.wait_for_function("[...document.querySelectorAll('.pdf-pages img')].slice(0,1).every(i => i.complete && i.naturalWidth > 1000)")
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


# ---------------- Ask the Portfolio voice agent ----------------
PREF = "Open to fully remote Senior Azure DevOps Engineer, Site Reliability Engineer (SRE) and Azure Infrastructure Engineer roles only."


def open_page(browser, rel, *scripts, **ctx):
    context = browser.new_context(**ctx)
    for sc in scripts:
        context.add_init_script(sc)
    page = context.new_page()
    page.goto(BASE + rel)
    return page


def agent_ask(page, q):
    expect(page.locator(".agent-log .msg.bot").first).to_be_visible()  # greeting loaded
    n = page.locator(".agent-log .msg.bot").count()
    page.fill("#agent-input", q)
    page.press("#agent-input", "Enter")
    expect(page.locator(".agent-log .msg.bot")).to_have_count(n + 1)
    return page.locator(".agent-log .msg.bot").last


@pytest.mark.parametrize("rel", ["index.html", "projects/aks-delivery-platform.html", "demos/azure-dr-restore-drill.html"]
                         + (["resume.html"] if HAS_RESUME else []))
def test_agent_available_on_every_page(browser, rel):
    page = open_page(browser, rel, NO_SPEECH)
    fab = page.locator(".agent-fab")
    expect(fab).to_be_visible()
    fab.click()
    panel = page.locator("#ask[role=dialog]")
    expect(panel).to_be_visible()
    expect(page.locator("#agent-input")).to_be_focused()
    expect(page.locator(".agent-log .msg.bot").first).to_contain_text(PREF)
    page.keyboard.press("Escape")
    expect(panel).to_be_hidden()
    expect(fab).to_be_focused()


def test_agent_text_question_and_follow_up(browser):
    page = open_page(browser, "index.html", NO_SPEECH)
    page.click(".agent-fab")
    a = agent_ask(page, "Who was his previous employer?")
    expect(a).to_contain_text("Work experience · from resume")
    expect(a).to_contain_text("most recent employer is Pulse Data Labs")
    b = agent_ask(page, "What were the results there?")
    expect(b).to_contain_text("no measured figures for this role")
    assert "10+" not in b.inner_text()
    # suggestion chips continue the conversation
    page.locator(".agent-chips .chip", has_text="What did he do at Teknip").click()
    expect(page.locator(".agent-log .msg.bot").last).to_contain_text("client MITIE")
    href = page.locator(".agent-log .msg.bot").last.locator("a", has_text="View resume").get_attribute("href")
    assert href.endswith("resume.html")


def test_agent_voice_question_is_spoken(browser):
    page = open_page(browser, "index.html", "window.__srMode='speak'; window.__phrase='Is he open to remote roles?';" + FAKE_SR, FAKE_TTS)
    page.wait_for_timeout(300)
    assert page.evaluate("window.__rec.length") == 0  # no microphone before a click
    page.click(".agent-fab")
    page.click("[data-agent-mic]")
    expect(page.locator(".agent-log .msg.user").last).to_have_text("Is he open to remote roles?")
    expect(page.locator(".agent-log .msg.bot").last).to_contain_text(PREF)
    page.wait_for_function("window.__spoken.length > 0")
    assert PREF in spoken(page)
    assert page.evaluate("window.__rec[0].lang") == "en-US"


def test_agent_hands_free_follow_up(browser):
    page = open_page(browser, "index.html", "window.__srMode='speak'; window.__phrase='Explain the AKS delivery platform';" + FAKE_SR, FAKE_TTS)
    page.click(".agent-fab")
    page.check("[data-agent-handsfree]")
    page.click("[data-agent-mic]")
    expect(page.locator(".agent-log .msg.bot").last).to_contain_text("AKS Delivery Platform", timeout=10000)
    page.evaluate("window.__phrase='What tools does it use?'")
    # after the spoken answer ends, the mic re-opens for the follow-up without another click
    expect(page.locator(".agent-log .msg.user").nth(1)).to_have_text("What tools does it use?", timeout=20000)
    second = page.locator(".agent-log .msg.bot").nth(2)
    expect(second).to_contain_text("Tools and services: Azure Pipelines")
    assert "Problem" not in second.inner_text()
    page.click("[data-agent-close]")  # closing stops listening and audio


def test_explain_this_project(browser):
    page = open_page(browser, "projects/azure-hub-spoke-terraform.html", FAKE_TTS)
    page.click("[data-explain]")
    msg = page.locator(".agent-log .msg.bot").last
    expect(msg).to_contain_text("Guided tour · scripted from the case study")
    for h in ("Problem:", "Architecture:", "Tools:", "Implementation:", "Documented outcome:"):
        expect(msg).to_contain_text(h)
    expect(msg).to_contain_text("not an employer result")
    page.wait_for_function("window.__spoken.length > 0")
    assert spoken(page).startswith("Guided tour of Azure Hub-and-Spoke")
    home_page = open_page(browser, "index.html", NO_SPEECH)
    assert home_page.locator("[data-explain]").count() == 6


def test_agent_reports_missing_information(browser):
    page = open_page(browser, "index.html", NO_SPEECH)
    page.click(".agent-fab")
    r = agent_ask(page, "What is his salary expectation?")
    expect(r).to_contain_text("Not in this portfolio")
    expect(r).to_contain_text("I don't have that information")


def test_agent_uses_endpoint_and_falls_back(browser):
    set_ep = """new MutationObserver((m, o) => { if (document.body) { document.body.setAttribute('data-agent-endpoint', 'https://agent.example.test/ask'); o.disconnect(); } })
                .observe(document, {childList: true, subtree: true});"""
    page = open_page(browser, "index.html", NO_SPEECH, set_ep)
    seen = []
    def ok(route):
        seen.append(route.request.post_data_json)
        route.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"},
                      body='{"answer": "From his resume: Pulse Data Labs, client URUS."}')
    page.route("https://agent.example.test/ask", ok)
    page.click(".agent-fab")
    expect(page.locator("[data-agent-mode]")).to_have_text("AI answers grounded in the resume and case studies")
    a = agent_ask(page, "Where did he work last?")
    expect(a).to_contain_text("AI answer · grounded in portfolio content")
    expect(a).to_contain_text("From his resume: Pulse Data Labs")
    assert seen[0]["question"] == "Where did he work last?"
    page.unroute("https://agent.example.test/ask")
    page.route("https://agent.example.test/ask", lambda r: r.fulfill(status=502, body="", headers={"Access-Control-Allow-Origin": "*"}))
    b = agent_ask(page, "Is he open to remote roles?")
    expect(b).to_contain_text("The AI service didn't respond")
    expect(b).to_contain_text(PREF)


def test_agent_on_phone(browser):
    page = open_page(browser, "index.html", NO_SPEECH, viewport={"width": 375, "height": 740}, is_mobile=True, has_touch=True)
    page.click(".menu-toggle")
    page.click("#site-nav .nav-ask")
    panel = page.locator("#ask")
    expect(panel).to_be_visible()
    agent_ask(page, "Explain the SRE lab")
    box = panel.bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 375.5 and box["y"] >= 0, box
    assert page.evaluate("document.documentElement.scrollWidth") <= 375
    expect(page.locator("#agent-input")).to_be_in_viewport()
