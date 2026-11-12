#!/usr/bin/env python3
"""Add clickable GitHub Portfolio and GitHub Repositories links to a copy of the resume.

  python tools/update_resume.py ORIGINAL.docx \
      --portfolio-url https://gollapudisrinu18.github.io/my-profile/ \
      --repo-url https://github.com/gollapudisrinu18/my-profile \
      --out Srinivasa_Rao_Gollapudi_Azure_DevOps_SRE_Resume_Updated.docx [--pdf]

The original file is not modified. A new line is inserted directly below the
paragraph that holds the contact details, reusing that paragraph's formatting
(shading, borders, font), so the line reads as part of the contact band.
With --pdf, LibreOffice exports a PDF next to the DOCX and the script checks
that both links are clickable in the PDF.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from xml.sax.saxutils import escape

W_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"


def find_paragraph(xml, marker):
    i = xml.find(marker)
    if i < 0:
        sys.exit(f"could not find '{marker}' in the document")
    start = max(xml.rfind("<w:p>", 0, i), xml.rfind("<w:p ", 0, i))
    end = xml.find("</w:p>", i) + len("</w:p>")
    return start, end


def run(rpr, text, underline=False):
    props = rpr
    if underline:
        props = props.replace("</w:rPr>", '<w:u w:val="single"/></w:rPr>') if props else '<w:rPr><w:u w:val="single"/></w:rPr>'
    return f'<w:r>{props}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def display(url):
    return re.sub(r"^https?://", "", url).rstrip("/")


def build_paragraph(contact_p, links):
    ppr = re.search(r"<w:pPr>.*?</w:pPr>", contact_p, re.S)
    ppr = ppr.group(0) if ppr else ""
    rpr = re.search(r"<w:rPr>.*?</w:rPr>", contact_p.split("</w:pPr>")[-1], re.S)
    rpr = rpr.group(0) if rpr else ""
    parts = []
    for n, (label, rid, url) in enumerate(links):
        if n:
            parts.append(run(rpr, "  |  "))
        parts.append(run(rpr, f"{label}: "))
        parts.append(f'<w:hyperlink r:id="{rid}" w:history="1">{run(rpr, display(url), underline=True)}</w:hyperlink>')
    return f"<w:p>{ppr}{''.join(parts)}</w:p>"


def update(src, out, portfolio_url, repo_url, marker):
    tmp = tempfile.mkdtemp()
    with zipfile.ZipFile(src) as z:
        names = z.namelist()
        z.extractall(tmp)
    doc_path = os.path.join(tmp, "word", "document.xml")
    rels_path = os.path.join(tmp, "word", "_rels", "document.xml.rels")
    xml = open(doc_path, encoding="utf-8").read()
    rels = open(rels_path, encoding="utf-8").read()
    if portfolio_url in rels:
        sys.exit("links already present - pass the original resume, not an updated one")

    if 'xmlns:r="' not in xml[:3000]:
        xml = xml.replace("<w:document ", '<w:document xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ', 1)
    ids = [int(x) for x in re.findall(r'Id="rId(\d+)"', rels)]
    rid_p, rid_r = f"rId{max(ids) + 1}", f"rId{max(ids) + 2}"
    rels = rels.replace("</Relationships>",
                        f'<Relationship Id="{rid_p}" Type="{W_REL}" Target="{escape(portfolio_url)}" TargetMode="External"/>'
                        f'<Relationship Id="{rid_r}" Type="{W_REL}" Target="{escape(repo_url)}" TargetMode="External"/>'
                        "</Relationships>")

    start, end = find_paragraph(xml, marker)
    new_p = build_paragraph(xml[start:end], [("GitHub Portfolio", rid_p, portfolio_url),
                                             ("GitHub Repositories", rid_r, repo_url)])
    xml = xml[:end] + new_p + xml[end:]
    open(doc_path, "w", encoding="utf-8").write(xml)
    open(rels_path, "w", encoding="utf-8").write(rels)

    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in names:  # keep original order, [Content_Types].xml first
            if name.endswith("/"):
                continue
            z.write(os.path.join(tmp, name), name)
    shutil.rmtree(tmp)


def export_pdf(docx):
    outdir = os.path.dirname(os.path.abspath(docx))
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", outdir, docx],
                   check=True, capture_output=True)
    return os.path.splitext(docx)[0] + ".pdf"


def pdf_links(pdf):
    from pypdf import PdfReader
    found = []
    for page in PdfReader(pdf).pages:
        for a in page.get("/Annots") or []:
            obj = a.get_object()
            uri = obj.get("/A", {}).get("/URI")
            if uri:
                found.append(str(uri))
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("original")
    ap.add_argument("--portfolio-url", required=True)
    ap.add_argument("--repo-url", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--marker", default="gollapudi.srinu18@gmail.com",
                    help="text inside the contact-details paragraph")
    ap.add_argument("--pdf", action="store_true")
    a = ap.parse_args()
    update(a.original, a.out, a.portfolio_url, a.repo_url, a.marker)
    print("wrote", a.out)
    if a.pdf:
        pdf = export_pdf(a.out)
        links = pdf_links(pdf)
        ok = a.portfolio_url in links and a.repo_url in links
        print("wrote", pdf, "| clickable links:", links, "|", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
