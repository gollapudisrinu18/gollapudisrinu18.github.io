"""Browsable source pages for the portfolio labs (source/ on the website).

Every committed file under projects/<dir>/ gets its own page: Markdown is rendered,
code is syntax-highlighted with line numbers, and each page shows the project's file
tree and the MIT license notice. Only files tracked by git are published, and the
build stops if a file looks like a secret, so nothing private reaches the site.
"""
import fnmatch
import html
import os
import posixpath
import re
import subprocess

import markdown
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_for_filename, guess_lexer_for_filename
from pygments.util import ClassNotFound

# Never published, even if they were ever committed.
EXCLUDE = ["*.pem", "*.key", "*.pfx", "*.p12", "id_rsa*", ".env", ".env.*", "*.tfstate", "*.tfstate.*",
           "local.settings.json", "backend.hcl", "*.sig.json", "*.pyc", "terraform.tfvars"]
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AccountKey=[A-Za-z0-9+/=]{20,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bxox[abp]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)client_secret\s*[:=]\s*['\"][^'\"$<{]{8,}['\"]"),
    re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),   # subscription/tenant IDs
]
EXTRA_LEXERS = {"Dockerfile": "docker", ".dockerignore": "text", ".trivyignore": "text",
                ".tf": "terraform", ".tfvars": "terraform", ".hcl": "terraform", ".tpl": "text", ".example": None}
FORMATTER = HtmlFormatter(linenos="table", cssclass="hl", anchorlinenos=True, lineanchors="L", wrapcode=True)


def pygments_css():
    return HtmlFormatter(style="github-dark", cssclass="hl").get_style_defs(".hl")


def tracked_files(root, rel_dir):
    out = subprocess.run(["git", "-C", root, "ls-files", "-z", "--", rel_dir], capture_output=True, check=True)
    files = [f for f in out.stdout.decode().split("\0") if f]
    return sorted(f for f in files if not any(fnmatch.fnmatch(posixpath.basename(f), pat) for pat in EXCLUDE))


def check_secrets(path, text):
    for pat in SECRET_PATTERNS:
        if pat.search(text):
            raise SystemExit(f"refusing to publish {path}: it matches the secret pattern {pat.pattern!r}")


def lexer_for(name, text):
    base = posixpath.basename(name)
    stem, ext = os.path.splitext(base)
    if ext == ".example":                       # e.g. terraform.tfvars.example -> terraform.tfvars
        return lexer_for(stem, text)
    key = base if base in EXTRA_LEXERS else ext
    if key in EXTRA_LEXERS and EXTRA_LEXERS[key]:
        from pygments.lexers import get_lexer_by_name
        return get_lexer_by_name(EXTRA_LEXERS[key])
    try:
        return get_lexer_for_filename(base, text)
    except ClassNotFound:
        try:
            return guess_lexer_for_filename(base, text)
        except ClassNotFound:
            return TextLexer()


def build_tree(paths):
    """{name: subtree or None} from relative file paths."""
    tree = {}
    for p in paths:
        node = tree
        parts = p.split("/")
        for part in parts[:-1]:
            node = node.setdefault(part + "/", {})
        node[parts[-1]] = None
    return tree


def render_tree(tree, prefix, href_root, current, open_dirs):
    items = []
    for name in sorted(tree, key=lambda n: (not n.endswith("/"), n.lower())):
        sub = tree[name]
        if sub is None:
            rel = prefix + name
            cur = ' aria-current="page"' if rel == current else ""
            items.append(f'<li class="f"><a href="{href_root}{html.escape(rel)}.html"{cur}>{html.escape(name)}</a></li>')
        else:
            d = prefix + name
            is_open = " open" if d in open_dirs else ""
            items.append(f'<li class="d"><details{is_open}><summary>{html.escape(name[:-1])}</summary>'
                         f'{render_tree(sub, d, href_root, current, open_dirs)}</details></li>')
    return "<ul>" + "".join(items) + "</ul>"


LINK = re.compile(r'(href|src)="([^"#:?]+)(#[^"]*)?"')


def fix_links(body, file_rel, files, href_root):
    """Point relative links in rendered Markdown at the matching source pages."""
    here = posixpath.dirname(file_rel)

    def sub(m):
        attr, target, frag = m.group(1), m.group(2), m.group(3) or ""
        if target.startswith("/"):
            return m.group(0)
        resolved = posixpath.normpath(posixpath.join(here, target)).lstrip("./") if target else file_rel
        if resolved in files:
            return f'{attr}="{href_root}{resolved}.html{frag}"'
        dir_index = [f for f in files if f.startswith(resolved.rstrip("/") + "/")]
        if dir_index:
            first = next((f for f in dir_index if posixpath.basename(f) == "README.md"), dir_index[0])
            return f'{attr}="{href_root}{first}.html{frag}"'
        return m.group(0)
    return LINK.sub(sub, body)


def render_markdown(text):
    """Markdown to HTML, with headings shifted down one level (the page already has its own h1)."""
    body = markdown.markdown(text, extensions=["fenced_code", "tables", "codehilite", "sane_lists"],
                             extension_configs={"codehilite": {"css_class": "hl", "guess_lang": False}})
    return re.sub(r"<(/?)h([1-5])\b", lambda m: f"<{m.group(1)}h{int(m.group(2)) + 1}", body)


def build(root, projects, write, license_text):
    """Write source/ pages. `write(rel_path, template, **ctx)` renders a site template."""
    summary = []
    for pr in projects:
        rel_dir = f"projects/{pr['dir']}"
        files = [f[len(rel_dir) + 1:] for f in tracked_files(root, rel_dir)]
        tree = build_tree(files)
        base = f"source/{pr['slug']}/"
        texts = {}
        for f in files:
            full = os.path.join(root, rel_dir, f)
            with open(full, encoding="utf-8") as fh:
                texts[f] = fh.read()
            check_secrets(full, texts[f])
        readme = texts.get("README.md", "")
        depth_root = "../" * (base.count("/"))
        write(base + "index.html", "source.html", p=pr, nav="projects", kind="index", files=files,
              tree_html=render_tree(tree, "", "", None, set()),
              body=fix_links(render_markdown(readme), "README.md", set(files), ""),
              path=None, lines=None, total=len(files))
        for f in files:
            text = texts[f]
            fset = set(files)
            open_dirs = {"/".join(f.split("/")[:k]) + "/" for k in range(1, f.count("/") + 1)}
            href_root = "../" * f.count("/")
            if f.lower().endswith(".md"):
                body = fix_links(render_markdown(text), f, fset, href_root)
                code = highlight(text, lexer_for(f, text), FORMATTER)
            else:
                body = None
                code = highlight(text, lexer_for(f, text), FORMATTER)
            write(base + f + ".html", "source.html", p=pr, nav="projects", kind="file", files=files,
                  tree_html=render_tree(tree, "", href_root, f, open_dirs), body=body, code=code,
                  path=f, lines=text.count("\n") + (0 if text.endswith("\n") else 1), total=len(files),
                  tree_root=href_root)
        summary.append({"p": pr, "count": len(files)})
    write("source/index.html", "source_list.html", nav="projects", items=summary, license_text=license_text)
    write("source/LICENSE.html", "source_list.html", nav="projects", items=None, license_text=license_text)
    return sum(s["count"] for s in summary)
