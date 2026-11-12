"""Browser checks for the portfolio site and the voice assistant (Playwright + Chrome).

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


def page_with(browser, *scripts, **ctx):
    context = browser.new_context(**ctx)
    for s in scripts:
        context.add_init_script(s)
    page = context.new_page()
    page.goto(BASE + "index.html#ask")
    expect(page.locator(".status-text")).to_contain_text("Ready")
    return page


def test_text_question_and_labelled_answer(browser):
    page = page_with(browser, NO_SPEECH)
    page.fill("#ask-input", "What is your Azure DevOps experience?")
    page.click(".ask-form button[type=submit]")
    bot = page.locator(".msg.bot").last
    expect(bot).to_contain_text("Work experience")
    expect(bot).to_contain_text("10+ applications")
    expect(bot.locator(".lab-note")).to_contain_text("Portfolio lab result")
    expect(bot.locator("a", has_text="AKS delivery case study")).to_have_attribute("href", "./projects/aks-delivery-platform.html")


def test_sample_question_lab_and_incident_labels(browser):
    page = page_with(browser, NO_SPEECH)
    page.click("[data-sample='How does the AKS rollback work?']")
    expect(page.locator(".msg.bot").last).to_contain_text("Portfolio lab result")
    page.click("[data-sample='Show me the SRE incident demo']")
    last = page.locator(".msg.bot").last
    expect(last).to_contain_text("Simulated incident")
    last.locator("a", has_text="Interactive walkthrough").click()
    expect(page).to_have_url(re.compile(r"demos/aks-observability-sre-lab\.html$"))


def test_unavailable_information(browser):
    page = page_with(browser, NO_SPEECH)
    page.fill("#ask-input", "What is his salary expectation?")
    page.press("#ask-input", "Enter")
    expect(page.locator(".msg.bot").last).to_contain_text("I don't have that information")


def test_fallback_when_speech_recognition_unavailable(browser):
    page = page_with(browser, NO_SPEECH)
    expect(page.locator(".mic")).to_be_disabled()
    expect(page.locator(".status-text")).to_contain_text("Ready")
    assert "isn't available in this browser" in page.locator(".mic").get_attribute("title")


def test_microphone_permission_denied(browser):
    page = page_with(browser, "window.__srMode='denied';" + FAKE_SR, FAKE_TTS)
    page.click(".mic")
    expect(page.locator(".status")).to_have_class(re.compile("error"))
    expect(page.locator(".status-text")).to_contain_text("Microphone permission was denied")
    expect(page.locator(".mic")).to_be_disabled()
    page.fill("#ask-input", "Tell me about Srinivasa")      # typing still works
    page.press("#ask-input", "Enter")
    expect(page.locator(".msg.bot").last).to_contain_text("11+ years")


def test_listening_status_and_stop(browser):
    page = page_with(browser, "window.__srMode='hold';" + FAKE_SR, FAKE_TTS)
    page.click(".mic")
    expect(page.locator(".status")).to_have_class(re.compile("listening"))
    expect(page.locator(".status-text")).to_contain_text("Listening (English)")
    expect(page.locator(".mic")).to_have_attribute("aria-pressed", "true")
    expect(page.locator(".stop")).to_be_enabled()
    page.click(".stop")
    assert page.evaluate("window.__rec[0].aborted") is True
    expect(page.locator(".status-text")).to_contain_text("Stopped")


def test_voice_question_answered_and_read_aloud(browser):
    page = page_with(browser, "window.__srMode='speak'; window.__phrase='How does the AKS rollback work?';" + FAKE_SR, FAKE_TTS)
    page.check("#speak-answers")
    page.click(".mic")
    expect(page.locator(".msg.user").last).to_have_text("How does the AKS rollback work?")
    expect(page.locator(".msg.bot").last).to_contain_text("helm rollback")
    page.wait_for_function("window.__spoken.some(s => s.text.includes('helm rollback'))")
    spoken = page.evaluate("window.__spoken[0]")
    assert spoken["lang"].startswith("en")
    assert page.evaluate("window.__rec[0].lang") == "en-US"


def test_no_autoplay_before_interaction(browser):
    page = page_with(browser, "window.__srMode='speak';" + FAKE_SR, FAKE_TTS)
    page.wait_for_timeout(500)
    assert page.evaluate("window.__rec.length") == 0
    assert page.evaluate("window.__spoken.length") == 0


def test_telugu_voice_input_and_playback(browser):
    tts = "window.__voices=[{lang:'en-US',name:'E'},{lang:'te-IN',name:'Telugu'}];" + FAKE_TTS
    page = page_with(browser, "window.__srMode='speak'; window.__phrase='శ్రీనివాస గురించి చెప్పండి';" + FAKE_SR, tts)
    page.select_option("#ask-lang", "te")
    page.check("#speak-answers")
    page.click(".mic")
    expect(page.locator(".msg.bot").last).to_contain_text("అనుభవం")
    assert page.evaluate("window.__rec[0].lang") == "te-IN"
    page.wait_for_function("window.__spoken.length > 0")
    assert page.evaluate("window.__spoken[0].lang") == "te-IN"


def test_telugu_without_telugu_voice_shows_text(browser):
    page = page_with(browser, NO_SPEECH, FAKE_TTS)  # only an English voice installed
    page.select_option("#ask-lang", "te")
    page.check("#speak-answers")
    page.fill("#ask-input", "శ్రీనివాస గురించి చెప్పండి")
    page.press("#ask-input", "Enter")
    expect(page.locator(".msg.bot").last).to_contain_text("అనుభవం")
    expect(page.locator(".status-text")).to_contain_text("No Telugu voice")
    assert page.evaluate("window.__spoken.length") == 0


def test_telugu_recognition_unsupported(browser):
    page = page_with(browser, "window.__srMode='unsupported-lang';" + FAKE_SR, FAKE_TTS)
    page.select_option("#ask-lang", "te")
    page.click(".mic")
    expect(page.locator(".status-text")).to_contain_text("తెలుగు voice input isn't supported")


def test_real_chrome_speech_api_denied_permission(browser):
    """Real Chrome Web Speech API with no microphone permission granted."""
    context = browser.new_context()
    page = context.new_page()
    page.goto(BASE + "index.html#ask")
    expect(page.locator(".status-text")).to_contain_text("Ready")
    if not page.evaluate("window.__portfolioAssistant.hasRecognition"):
        pytest.skip("this Chrome build has no SpeechRecognition")
    page.click(".mic")
    expect(page.locator(".status")).to_have_class(re.compile("error"), timeout=10000)
    print("real Chrome message:", page.locator(".status-text").inner_text())


def test_transcripts_not_stored(browser):
    page = page_with(browser, NO_SPEECH)
    page.fill("#ask-input", "Tell me about Srinivasa")
    page.press("#ask-input", "Enter")
    expect(page.locator(".msg.bot")).to_have_count(1)
    page.click("h1")  # may set the welcome's session flag; questions must still not be stored
    assert page.evaluate("localStorage.length") == 0
    stored = page.evaluate("JSON.stringify(Object.assign({}, sessionStorage))")
    assert "Srinivasa" not in stored and "years" not in stored
    assert set(page.evaluate("Object.keys(sessionStorage)")) <= {"portfolio.welcome.autoplayed", "portfolio.welcome.muted"}
    assert page.evaluate("document.cookie") == ""
    page.reload()
    expect(page.locator(".msg")).to_have_count(0)


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
           "or take a short tour of the project architectures.")
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
    assert labels == (["Experience", "Projects", "Architecture", "Resume", "Ask"] if HAS_RESUME
                      else ["Experience", "Projects", "Architecture", "Ask"])


def test_hero_actions_and_outcomes(browser):
    page = home(browser, NO_SPEECH)
    hero = page.locator(".hero")
    expect(hero.locator(".headline")).to_have_text("Senior Azure DevOps Engineer | Site Reliability Engineer (SRE)")
    for fact in ("11+ years in IT", "Immediate joiner", "Remote only", "Bangalore, India"):
        expect(hero.locator(".facts")).to_contain_text(fact)
    primaries = [b.inner_text() for b in hero.locator(".cta-primary .btn.primary").all()]
    assert primaries == (["View Projects", "View Resume"] if HAS_RESUME else ["View Projects"])
    secondary = [b.inner_text() for b in hero.locator(".cta-secondary .btn").all()]
    assert secondary[:2] == ["▶ Play intro", "Start Portfolio Tour"], secondary
    assert hero.locator(".cta-secondary .btn.primary").count() == 0
    assert page.locator("[data-tour-start]").count() == 1
    assert "Senior Azure DevOps Engineer" not in hero.locator(".lead").inner_text()
    assert page.locator("text=Download Resume").count() == 0
    assert page.locator("a[href*='linkedin']").count() == 0
    out = page.locator(".outcomes")
    expect(out).to_contain_text("Professional experience")
    expect(out).to_contain_text("MITIE")
    for t in ("10+ applications deployed to AKS", "Release lead time reduced from days to hours", "~45% fewer false-positive alerts"):
        expect(out).to_contain_text(t)
    snap = page.locator(".outcomes ul").aria_snapshot()
    assert snap.count("10+") == 1 and snap.count("45%") == 1, snap


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
    assert page.evaluate("window.__paused") == 1
    toggle.click()
    expect(toggle).to_have_text("Pause")
    assert page.evaluate("window.__resumed") >= 1
    page.click("[data-intro-stop]")
    expect(toggle).to_have_text("Play")
    expect(page.locator("[data-intro-status]")).to_contain_text("stopped")
    assert page.evaluate("window.speechSynthesis.speaking") is False
    expect(page.locator("[data-intro-stop]")).to_be_disabled()
    assert page.evaluate("window.__rec.length") == 0


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
    assert page.evaluate("window.__paused") == 1
    play.click()
    expect(play).to_have_text("Pause narration")
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


def test_typed_questions_work_with_microphone_blocked(browser):
    page = page_with(browser, "window.__srMode='denied';" + FAKE_SR, NO_TTS)
    page.click(".mic")
    expect(page.locator(".status-text")).to_contain_text("Microphone permission was denied")
    page.fill("#ask-input", "How does the AKS rollback work?")
    page.press("#ask-input", "Enter")
    expect(page.locator(".msg.bot").last).to_contain_text("helm rollback")


def test_assistant_links_open_diagrams_and_pages(browser):
    page = page_with(browser, NO_SPEECH)
    page.click("[data-sample='How is the delivery pipeline designed?']")
    bot = page.locator(".msg.bot").last
    expect(bot).to_contain_text("Portfolio lab")
    bot.locator("a", has_text="Delivery diagram").click()
    expect(page.locator("#arch-delivery")).to_be_visible()
    page.fill("#ask-input", "Can I view his resume?")
    page.press("#ask-input", "Enter")
    bot = page.locator(".msg.bot").last
    if HAS_RESUME:
        bot.locator("a", has_text="View resume").click()
        expect(page).to_have_url(re.compile(r"resume\.html$"))
    else:
        expect(bot).to_contain_text("experience timeline")


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
    frame = page.locator("iframe.pdf-frame")
    src = frame.get_attribute("src")
    assert src.startswith("./assets/resume/") and ".pdf#toolbar=0" in src
    assert (SITE / "assets/resume/Srinivasa_Rao_Gollapudi_Resume.pdf").stat().st_size > 10000
    imgs = page.locator(".pdf-pages img")
    expect(imgs).to_have_count(3)
    # the PDF itself (or its page images) is the only visible resume; no download button
    assert page.locator("a[download], a[href$='.pdf'], a[href$='.docx']").count() == 0
    assert "Download" not in page.locator("main").inner_text()
    heads = [h.text_content() for h in page.locator("article.sr-only h3").all()]
    assert heads[0].startswith("Senior DevOps Engineer") and len(heads) == 4
    # phones: page images instead of the PDF frame
    m = browser.new_page(viewport={"width": 390, "height": 844})
    m.goto(BASE + "resume.html")
    expect(m.locator("iframe.pdf-frame")).to_be_hidden()
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
