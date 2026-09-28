# -*- coding: utf-8 -*-
"""(4) Extract visible text from report/index.html (html.parser), dropping <script>/<style> and base64 images."""
import sys, os, re
from html.parser import HTMLParser
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
class P(HTMLParser):
    def __init__(s):
        super().__init__(); s.out = []; s.skip = 0
    def handle_starttag(s, t, a):
        if t in ("script", "style"): s.skip += 1
        if t in ("h1", "h2", "h3", "h4"): s.out.append("\n\n### ")
        if t in ("p", "li", "tr", "div", "br", "summary", "figcaption", "details"): s.out.append("\n")
        if t in ("td", "th"): s.out.append(" | ")
        if t == "img":
            d = dict(a); s.out.append("[IMG alt=%s]" % d.get("alt", ""))
    def handle_endtag(s, t):
        if t in ("script", "style"): s.skip -= 1
    def handle_data(s, d):
        if not s.skip: s.out.append(d)
p = P(); p.feed(open(os.path.join(ROOT, "report", "index.html"), encoding="utf-8").read())
txt = re.sub(r"[ \t]+", " ", "".join(p.out)); txt = re.sub(r"\n\s*\n+", "\n", txt)
open(os.path.join(os.path.dirname(__file__), "index_text.txt"), "w", encoding="utf-8").write(txt)
print(len(txt))
