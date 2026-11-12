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
    last.locator("a", has_text="Play the demo").click()
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
    page.wait_for_function("window.__spoken.length > 0")
    spoken = page.evaluate("window.__spoken[0]")
    assert spoken["lang"] == "en-US" and "helm rollback" in spoken["text"]
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


# ---------------- recruiter-first homepage ----------------
WELCOME = ("Hi, I\u2019m Srinivasa\u2019s portfolio assistant. Would you like to see his Azure DevOps and SRE "
           "experience, explore a project, or ask me a question?")
# Speech that keeps "playing" until cancelled, to exercise the Stop and Mute controls.
HOLD_TTS = """
window.__spoken = [];
Object.defineProperty(window, 'speechSynthesis', {value: {
  speaking:false, getVoices(){ return [{lang:'en-US', name:'Test English'}]; },
  cancel(){ window.__cancelled=(window.__cancelled||0)+1; const u=this._u; this._u=null; this.speaking=false;
            if (u && u.onerror) u.onerror({error:'interrupted'}); },
  speak(u){ window.__spoken.push({text:u.text, lang:u.lang}); this._u=u; this.speaking=true; u.onstart && u.onstart(); }
}});
window.SpeechSynthesisUtterance = function(t){ this.text=t; };
"""
BLOCKED_TTS = """
window.__spoken = [];
Object.defineProperty(window, 'speechSynthesis', {value: {
  speaking:false, getVoices(){ return []; }, cancel(){},
  speak(u){ window.__spoken.push({text:u.text}); setTimeout(()=>u.onerror&&u.onerror({error:'not-allowed'}), 20); }
}});
window.SpeechSynthesisUtterance = function(t){ this.text=t; };
"""
NO_TTS = "delete window.speechSynthesis; delete window.SpeechSynthesisUtterance;"


def home(browser, *scripts, **ctx):
    context = browser.new_context(**ctx)
    for s in scripts:
        context.add_init_script(s)
    page = context.new_page()
    page.goto(BASE + "index.html")
    expect(page.locator("[data-welcome]")).to_be_visible()
    return page


def test_hero_is_recruiter_first(browser):
    page = home(browser, NO_SPEECH)
    hero = page.locator(".hero")
    expect(hero.locator(".headline")).to_have_text("Senior Azure DevOps Engineer | Site Reliability Engineer (SRE)")
    lead = hero.locator(".lead").inner_text()
    assert lead.count(". ") + 1 == 2 and "11+ years in IT" in lead
    for word in ("Azure DevOps", "AKS", "Terraform", "SRE" if "SRE" in lead else "SLO"):
        assert word in lead
    impact = hero.locator(".impact")
    expect(impact).to_contain_text("professional experience")
    expect(impact).to_contain_text("10+ applications deployed to AKS")
    expect(impact).to_contain_text("Release lead time reduced from days to hours")
    expect(impact).to_contain_text("~45% fewer false-positive alerts")
    for fact in ("11+ years in IT", "Immediate joiner", "Remote only", "Bangalore, India"):
        expect(hero.locator(".facts")).to_contain_text(fact)
    # No resume / LinkedIn / email configured -> View Projects is the primary action and nothing broken ships.
    expect(hero.locator(".cta .btn.primary")).to_have_text("View Projects")
    assert hero.locator("[data-cta=resume], [data-contact]").count() == 0


def test_lead_case_studies_first_and_all_six_linked(browser):
    page = home(browser, NO_SPEECH)
    cards = page.locator("#projects .lead-card")
    expect(cards).to_have_count(2)
    assert cards.nth(0).get_attribute("data-lead") == "aks-delivery-platform"
    assert cards.nth(1).get_attribute("data-lead") == "aks-observability-sre-lab"
    expect(cards.nth(0)).to_contain_text("1.1.0")
    expect(cards.nth(0)).to_contain_text("1.0.0")
    for step in ("Alert", "Investigation", "Mitigation", "Postmortem"):
        expect(cards.nth(1).locator(".verify")).to_contain_text(step)
    for i, slug in enumerate(["aks-delivery-platform", "aks-observability-sre-lab"]):
        expect(cards.nth(i).locator(".lead-actions .btn.primary")).to_have_attribute("href", f"./projects/{slug}.html")
        expect(cards.nth(i).locator(".lead-actions a", has_text="Watch Demo")).to_have_attribute("href", f"./demos/{slug}.html")
    for slug in ["aks-delivery-platform", "azure-hub-spoke-terraform", "aks-observability-sre-lab",
                 "azure-devsecops-supply-chain", "azure-functions-event-processing", "azure-dr-restore-drill"]:
        assert page.locator(f"#projects a[href='./projects/{slug}.html']").count() >= 1, slug
        assert page.locator(f"#projects a[href='./demos/{slug}.html']").count() >= 1, slug


def test_sample_questions_order_and_production_answer(browser):
    page = page_with(browser, NO_SPEECH)
    samples = page.locator("[data-sample]")
    assert [samples.nth(i).inner_text() for i in range(3)] == [
        "What Azure DevOps work has Srinivasa done in production?",
        "How does the AKS rollback work?",
        "Show me the SRE incident demo"]
    samples.nth(0).click()
    bot = page.locator(".msg.bot").last
    expect(bot.locator(".kind").first).to_contain_text("Work experience")
    expect(bot).to_contain_text("MITIE")
    expect(bot.locator(".lab-note .badge")).to_have_text("Portfolio lab result")
    expect(bot.locator(".lab-note a", has_text="Watch the rollback demo")).to_have_attribute("href", "./demos/aks-delivery-platform.html")


def test_typing_is_primary_input(browser):
    page = page_with(browser, NO_SPEECH)
    expect(page.locator(".ask-form button[type=submit]")).to_have_class(re.compile("primary"))
    expect(page.locator(".mic")).not_to_have_class(re.compile("primary"))


def test_welcome_plays_once_on_first_interaction_without_microphone(browser):
    page = home(browser, FAKE_SR, FAKE_TTS)
    expect(page.locator("[data-welcome-text]")).to_have_text(WELCOME)
    page.wait_for_timeout(300)
    assert page.evaluate("window.__spoken.length") == 0       # nothing before an interaction
    page.click("h1")
    page.wait_for_function("window.__spoken.length === 1")
    assert page.evaluate("window.__spoken[0].text") == WELCOME
    page.click("h1")
    page.wait_for_timeout(200)
    assert page.evaluate("window.__spoken.length") == 1        # only once
    assert page.evaluate("window.__rec.length") == 0           # microphone never started
    # Opening a project page and returning in the same session does not repeat it...
    page.goto(BASE + "projects/aks-delivery-platform.html")
    page.goto(BASE + "index.html")
    page.click("h1")
    page.wait_for_timeout(300)
    assert page.evaluate("window.__spoken.length") == 0
    # ...but Play welcome always replays it.
    page.click("[data-welcome-play]")
    page.wait_for_function("window.__spoken.length === 1")
    assert page.evaluate("window.__rec.length") == 0


def test_welcome_stop_and_mute(browser):
    page = home(browser, FAKE_SR, HOLD_TTS)
    page.click("[data-welcome-play]")
    expect(page.locator("[data-welcome-stop]")).to_be_visible()
    page.click("[data-welcome-stop]")
    expect(page.locator("[data-welcome-stop]")).to_be_hidden()
    expect(page.locator("[data-welcome-status]")).to_contain_text("stopped")
    page.click("[data-welcome-play]")
    page.click("[data-welcome-mute]")
    expect(page.locator("[data-welcome-mute]")).to_have_attribute("aria-pressed", "true")
    expect(page.locator("[data-welcome-stop]")).to_be_hidden()
    assert page.evaluate("window.speechSynthesis.speaking") is False
    assert page.evaluate("window.__rec.length") == 0


def test_welcome_muted_does_not_autoplay(browser):
    page = home(browser, FAKE_TTS)
    page.click("[data-welcome-mute]")
    page.reload()
    expect(page.locator("[data-welcome-mute]")).to_have_attribute("aria-pressed", "true")
    page.click("h1")
    page.wait_for_timeout(300)
    assert page.evaluate("window.__spoken.length") == 0
    page.click("[data-welcome-play]")                     # explicit play still works
    page.wait_for_function("window.__spoken.length === 1")


def test_welcome_when_speech_is_unavailable(browser):
    page = home(browser, NO_TTS)
    expect(page.locator("[data-welcome-text]")).to_have_text(WELCOME)
    expect(page.locator("[data-welcome-play]")).to_be_disabled()
    expect(page.locator("[data-welcome-status]")).to_contain_text("isn't available")
    page.click("h1")                                        # no errors, greeting stays
    expect(page.locator("[data-welcome-text]")).to_be_visible()


def test_welcome_when_audio_is_blocked(browser):
    page = home(browser, BLOCKED_TTS)
    page.click("h1")
    expect(page.locator("[data-welcome-status]")).to_contain_text("blocked audio")
    expect(page.locator("[data-welcome-play]")).to_be_enabled()
    expect(page.locator("[data-welcome-text]")).to_be_visible()


def test_ask_a_question_focuses_input(browser):
    page = home(browser, NO_SPEECH, FAKE_TTS)
    page.click("[data-welcome-ask]")
    expect(page.locator("#ask-input")).to_be_focused()
    assert page.evaluate("window.__spoken.length") == 0


def test_welcome_keyboard_access(browser):
    page = home(browser, FAKE_SR, FAKE_TTS)
    page.locator("[data-welcome-play]").focus()
    page.keyboard.press("Enter")
    page.wait_for_function("window.__spoken.length === 1")
    page.locator("[data-welcome-ask]").focus()
    page.keyboard.press("Enter")
    expect(page.locator("#ask-input")).to_be_focused()
    assert page.evaluate("window.__rec.length") == 0


def test_mobile_welcome_does_not_cover_buttons(browser):
    page = home(browser, NO_SPEECH, viewport={"width": 390, "height": 844})
    card = page.locator("[data-welcome]").bounding_box()
    for btn in page.locator(".hero .cta .btn").all():
        b = btn.bounding_box()
        overlap = not (b["y"] + b["height"] <= card["y"] or card["y"] + card["height"] <= b["y"]
                       or b["x"] + b["width"] <= card["x"] or card["x"] + card["width"] <= b["x"])
        assert not overlap, btn.inner_text()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
