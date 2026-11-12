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
    expect(bot).to_contain_text("Career history")
    expect(bot).to_contain_text("10+ applications")
    expect(bot.locator("a", has_text="AKS Delivery Platform lab")).to_have_attribute("href", "./projects/aks-delivery-platform.html")


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
    assert page.evaluate("localStorage.length + sessionStorage.length") == 0
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
