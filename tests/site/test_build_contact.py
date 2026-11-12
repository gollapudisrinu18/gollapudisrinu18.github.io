"""Contact links are shown only when they are real: python -m pytest tests/site/test_build_contact.py"""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("build_site", os.path.join(HERE, "..", "..", "site", "build_site.py"))
build_site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_site)


def test_missing_values_are_hidden():
    assert build_site.check_contact({"contact": {"resume_pdf": "", "linkedin_url": "", "email": ""}}) == {}
    assert build_site.check_contact({}) == {}


def test_broken_values_are_dropped():
    out = build_site.check_contact({"contact": {
        "resume_pdf": "assets/resume/does-not-exist.pdf",
        "linkedin_url": "https://example.com/me",
        "email": "not-an-email"}})
    assert out == {}


def test_valid_values_are_kept(tmp_path):
    rel = "assets/_test_resume.pdf"
    path = os.path.join(build_site.STATIC, rel)
    with open(path, "wb") as fh:
        fh.write(b"%PDF-1.4\n%test\n")
    try:
        out = build_site.check_contact({"contact": {
            "resume_pdf": rel,
            "linkedin_url": "https://www.linkedin.com/in/example-person/",
            "email": "someone@example.com"}})
        assert out == {"resume_pdf": rel, "linkedin_url": "https://www.linkedin.com/in/example-person/",
                       "email": "someone@example.com"}
        entry = build_site.contact_entry(out)
        assert [l["label"] for l in entry["links"]][:3] == ["Download resume (PDF)", "LinkedIn", "Email"]
    finally:
        os.remove(path)
