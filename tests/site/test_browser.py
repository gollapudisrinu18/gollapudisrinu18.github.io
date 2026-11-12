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
        for ref in re.findall(r'(?:href|src)="([^"#]+)', text):
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
  speak(u){ window.__spoken.push({text:u.text, lang:u.lang}); this._u=u; this.speaking=true; u.onstart && u.onstart(); }
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
    expect(page.locator("[data-welcome]")).to_be_visible()
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
    expect(hero.locator(".cta .btn.primary")).to_have_text("View Projects")
    expect(hero.locator(".cta [data-cta=tour]")).to_have_text("Start Portfolio Tour")
    assert hero.locator(".cta [data-cta=resume]").count() == (1 if HAS_RESUME else 0)
    assert page.locator("text=Download Resume").count() == 0
    assert page.locator("a[href*='linkedin']").count() == 0
    out = page.locator(".outcomes")
    expect(out).to_contain_text("Professional experience")
    expect(out).to_contain_text("MITIE")
    for t in ("10+ applications deployed to AKS", "Release lead time reduced from days to hours", "~45% fewer false-positive alerts"):
        expect(out).to_contain_text(t)


def test_architecture_tabs_and_diagrams(browser):
    page = home(browser, NO_SPEECH)
    for key in ("delivery", "infrastructure", "reliability"):
        page.click(f"[data-tab={key}]")
        panel = page.locator(f"#arch-{key}")
        expect(panel).to_be_visible()
        expect(panel.locator("figcaption")).to_contain_text("Portfolio lab")
        svg = panel.locator("svg.arch-svg")
        assert svg.get_attribute("role") == "img"
        assert page.evaluate(f"document.querySelector('#arch-{key} svg').getBBox().width") > 700
        # arrowheads resolve to this diagram's own markers
        ids = page.evaluate(f"[...document.querySelectorAll('#arch-{key} [marker-end]')].map(e => e.getAttribute('marker-end'))")
        assert ids and all(i.startswith(f"url(#{key}-") for i in ids)
    # keyboard: arrow keys move between tabs
    page.focus("[data-tab=reliability]")
    page.keyboard.press("ArrowRight")
    expect(page.locator("[data-tab=delivery]")).to_be_focused()
    expect(page.locator("#arch-delivery")).to_be_visible()
    # deep link to a diagram
    page.goto(BASE + "index.html#arch-reliability")
    expect(page.locator("#arch-reliability")).to_be_visible()
    expect(page.locator("[data-tab=reliability]")).to_have_attribute("aria-selected", "true")


def test_projects_on_home_and_case_studies(browser):
    page = home(browser, NO_SPEECH)
    leads = page.locator("[data-lead]")
    assert [leads.nth(i).get_attribute("data-lead") for i in range(2)] == SLUGS[:2]
    for slug in SLUGS:
        assert page.locator(f"#projects a[href='./projects/{slug}.html']").count() >= 1, slug
    for slug in SLUGS:
        page.goto(BASE + f"projects/{slug}.html")
        for sid in ("problem", "environment", "architecture", "implementation", "decisions", "failure", "recovery",
                    "result", "walkthrough", "evidence"):
            expect(page.locator(f"section#{sid}")).to_have_count(1)
        expect(page.locator(".scope tbody tr").first).to_be_visible()
        expect(page.locator("#walkthrough h3", has_text="Recorded demo")).to_be_visible()
        expect(page.locator("#walkthrough video source")).to_have_attribute("src", f"../assets/video/{slug}.mp4")
        expect(page.locator("#walkthrough a", has_text="interactive walkthrough")).to_have_attribute("href", f"../demos/{slug}.html")
        assert page.locator(".diagram img").count() >= 1
    page.goto(BASE + "demos/aks-delivery-platform.html")
    expect(page.locator("h1")).to_contain_text("Interactive walkthrough")


def test_welcome_once_per_session_and_never_microphone(browser):
    page = home(browser, FAKE_SR, FAKE_TTS)
    expect(page.locator("[data-welcome-text]")).to_have_text(WELCOME)
    page.wait_for_timeout(400)
    assert page.evaluate("window.__spoken.length") == 0
    page.click("h1")
    page.wait_for_function("window.__spoken.length > 0")
    page.wait_for_timeout(300)
    assert spoken(page) == WELCOME
    n = page.evaluate("window.__spoken.length")
    page.click("h1")
    page.wait_for_timeout(200)
    assert page.evaluate("window.__spoken.length") == n
    page.goto(BASE + "projects/aks-delivery-platform.html")
    page.goto(BASE + "index.html")
    page.click("h1")
    page.wait_for_timeout(400)
    assert page.evaluate("window.__spoken.length") == 0
    page.click("[data-welcome-play]")
    page.wait_for_function("window.__spoken.length > 0")
    assert page.evaluate("window.__rec.length") == 0


def test_tour_controls_and_captions(browser):
    page = home(browser, FAKE_SR, HOLD_TTS)
    page.click(".cta [data-tour-start]")
    bar = page.locator("[data-tour]")
    expect(bar).to_be_visible()
    expect(bar.locator("[data-tour-step]")).to_have_text("Delivery · 1 of 4")
    expect(page.locator("#arch-delivery")).to_have_class(re.compile("tour-focus"))
    page.wait_for_function("window.__spoken.length > 0")
    assert window_text(page).startswith("Delivery.")
    page.click("[data-tour-next]")
    expect(bar.locator("[data-tour-step]")).to_have_text("Infrastructure · 2 of 4")
    expect(page.locator("[data-tab=infrastructure]")).to_have_attribute("aria-selected", "true")
    expect(page.locator("#arch-infrastructure")).to_be_visible()
    page.wait_for_function("window.speechSynthesis._u && window.speechSynthesis._u.text.startsWith('Infrastructure')")
    assert page.evaluate("window.__cancelled") >= 1           # previous narration stopped: no overlap
    page.click("[data-tour-back]")
    expect(bar.locator("[data-tour-caption]")).to_contain_text("Delivery.")
    page.click("[data-tour] [data-mute]")
    assert page.evaluate("window.speechSynthesis.speaking") is False
    expect(bar.locator("[data-tour-caption]")).to_contain_text("Delivery.")   # captions stay
    n = page.evaluate("window.__spoken.length")
    page.click("[data-tour-next]")
    page.wait_for_timeout(300)
    assert page.evaluate("window.__spoken.length") == n         # muted: no narration
    page.click("[data-tour] [data-mute]")                        # unmute
    page.wait_for_function(f"window.__spoken.length > {n}")
    page.click("[data-tour-stop]")
    expect(bar).to_be_hidden()
    assert page.evaluate("window.speechSynthesis.speaking") is False
    assert page.evaluate("window.__rec.length") == 0


def window_text(page):
    return page.evaluate("window.speechSynthesis._u ? window.speechSynthesis._u.text : ''")


def test_tour_finish_and_free_exploration(browser):
    page = home(browser, NO_SPEECH, FAKE_TTS)
    page.click(".cta [data-tour-start]")
    for _ in range(3):
        page.click("[data-tour-next]")
    expect(page.locator("[data-tour-next]")).to_have_text("Finish")
    expect(page.locator("#projects")).to_have_class(re.compile("tour-focus"))
    page.locator("#projects a", has_text="Case study").first.click()   # visitors can leave the tour at any time
    expect(page).to_have_url(re.compile(r"projects/aks-delivery-platform\.html$"))


def test_speech_failure_shows_friendly_fallback(browser):
    page = home(browser, failing_tts("synthesis-failed"))
    page.click(".cta [data-tour-start]")
    note = page.locator("[data-tour-note]")
    expect(note).to_contain_text("Audio couldn't start")
    expect(page.locator("[data-tour-retry]")).to_be_visible()
    expect(page.locator("[data-tour-caption]")).to_contain_text("Delivery.")
    assert page.evaluate("window.__spoken.length") == 2          # retried once with another voice
    page.click("[data-tour-retry]")
    expect(note).to_contain_text("Audio couldn't start")
    page.click("[data-tour-stop]")
    page.click("[data-welcome-play]")
    expect(page.locator("[data-welcome-status]")).to_contain_text("Audio couldn't start")
    assert not CODES.search(page.evaluate(STATUS_JS))


def test_blocked_and_silent_speech(browser):
    page = home(browser, failing_tts("not-allowed"))
    page.click("[data-welcome-play]")
    expect(page.locator("[data-welcome-status]")).to_contain_text("needs a click")
    page = home(browser, SILENT_TTS)                              # speech that never starts
    page.click("[data-welcome-play]")
    expect(page.locator("[data-welcome-status]")).to_contain_text("Audio couldn't start", timeout=10000)
    assert not CODES.search(page.evaluate(STATUS_JS))


def test_no_speech_support_keeps_text_tour(browser):
    page = home(browser, NO_TTS)
    expect(page.locator("[data-welcome-play]")).to_be_disabled()
    expect(page.locator("[data-welcome-status]")).to_contain_text("can't read text aloud")
    page.click(".cta [data-tour-start]")
    expect(page.locator("[data-tour-caption]")).to_contain_text("Delivery.")
    page.click("[data-tour-next]")
    expect(page.locator("[data-tour-caption]")).to_contain_text("Infrastructure.")


def test_speech_stops_when_leaving_page(browser):
    page = home(browser, HOLD_TTS)
    page.click(".cta [data-tour-start]")
    page.wait_for_function("window.speechSynthesis.speaking")
    page.evaluate("window.dispatchEvent(new PageTransitionEvent('pagehide'))")
    assert page.evaluate("window.speechSynthesis.speaking") is False


def test_tour_keyboard(browser):
    page = home(browser, NO_SPEECH, FAKE_TTS)
    page.locator(".cta [data-tour-start]").focus()
    page.keyboard.press("Enter")
    expect(page.locator("[data-tour-next]")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("[data-tour-step]")).to_contain_text("2 of 4")
    page.keyboard.press("Escape")
    expect(page.locator("[data-tour]")).to_be_hidden()


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
        expect(page.locator("h1")).to_be_visible()
    else:
        expect(bot).to_contain_text("experience timeline")


def test_mobile_layout(browser):
    page = home(browser, NO_SPEECH, viewport={"width": 390, "height": 844})
    card = page.locator("[data-welcome]").bounding_box()
    for btn in page.locator(".hero .cta .btn").all():
        b = btn.bounding_box()
        assert b["height"] >= 44
        assert b["y"] + b["height"] <= card["y"] or card["y"] + card["height"] <= b["y"], btn.inner_text()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.goto(BASE + "projects/aks-observability-sre-lab.html")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    if HAS_RESUME:
        page.goto(BASE + "resume.html")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
