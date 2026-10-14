#!/usr/bin/env python3
"""把 prototype/ch5-cards/ 下的卡片 Markdown 渲染成单文件手机可读 HTML 原型。

用法：python3 build.py
输出：prototype/index.html（自包含，mermaid 走 CDN，首次在线加载后浏览器缓存）
"""
import json
import re
import sys
from pathlib import Path

CARD_DIR = Path(__file__).parent / "ch5-cards"
OUT = Path(__file__).parent / "index.html"

TYPE_META = {
    "dilemma": ("困境卡", "🧭", "先自己想方案，再揭示代价"),
    "simulation": ("推演卡", "⏱", "逐步推演系统行为，先预测再看答案"),
    "incident": ("事故档案", "🔥", "真实事故叙事，记忆钩子"),
}


def parse_card(text: str) -> dict:
    lines = text.splitlines()
    meta = {}
    body_start = 0
    for i, line in enumerate(lines):
        m = re.match(r"^(\w+):\s*(.+)$", line)
        if m:
            meta[m.group(1)] = m.group(2).strip()
        elif line.strip():
            body_start = i
            break
    body = "\n".join(lines[body_start:])
    sections = {}
    # split by "## " headers
    parts = re.split(r"^## (.+)$", body, flags=re.M)
    # parts: [pre, name1, content1, name2, content2, ...]
    pre = parts[0].strip()
    if pre:
        sections["引言"] = pre
    for i in range(1, len(parts), 2):
        name = parts[i].strip()
        content = parts[i + 1].strip()
        sections[name] = content
    meta["sections"] = sections
    return meta


def md_inline(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s, flags=re.S)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s, flags=re.S)
    return s


def render_section(name: str, content: str) -> str:
    # code blocks (incl. mermaid) preserved separately
    blocks = []
    def stash(m):
        lang = m.group(1) or ""
        body = m.group(2)
        idx = len(blocks)
        blocks.append((lang, body))
        return f"\x00BLOCK{idx}\x00"

    content = re.sub(r"```(\w*)\n(.*?)```", stash, content, flags=re.S)

    html_parts = []
    in_ul = False
    in_ol = False
    in_quote = False
    para_buf = []
    def flush_para():
        nonlocal para_buf
        if para_buf:
            html_parts.append(f"<p>{md_inline(' '.join(para_buf))}</p>")
            para_buf = []
    for raw in content.split("\n"):
        line = raw.rstrip()
        stripped = line.strip()
        block_match = re.match(r"^\s*\x00BLOCK(\d+)\x00\s*$", stripped)
        if block_match:
            flush_para()
            lang, body = blocks[int(block_match.group(1))]
            if in_ul:
                html_parts.append("</ul>"); in_ul = False
            if in_ol:
                html_parts.append("</ol>"); in_ol = False
            if lang == "mermaid":
                html_parts.append(
                    f'<div class="mermaid-wrap"><pre class="mermaid">{body}</pre></div>'
                )
            else:
                import html as h
                html_parts.append(f"<pre class=\"code\"><code>{h.escape(body)}</code></pre>")
            in_quote = False
            continue
        if not stripped:
            flush_para()
            if in_ul: html_parts.append("</ul>"); in_ul = False
            if in_ol: html_parts.append("</ol>"); in_ol = False
            if in_quote: html_parts.append("</blockquote>"); in_quote = False
            continue
        if stripped.startswith("- "):
            flush_para()
            if in_quote: html_parts.append("</blockquote>"); in_quote = False
            if in_ol: html_parts.append("</ol>"); in_ol = False
            if not in_ul:
                html_parts.append("<ul>"); in_ul = True
            html_parts.append(f"<li>{md_inline(stripped[2:])}</li>")
            continue
        m_ol = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m_ol:
            flush_para()
            if in_quote: html_parts.append("</blockquote>"); in_quote = False
            if in_ul: html_parts.append("</ul>"); in_ul = False
            if not in_ol:
                html_parts.append("<ol>"); in_ol = True
            html_parts.append(f"<li>{md_inline(m_ol.group(2))}</li>")
            continue
        if stripped.startswith("> "):
            flush_para()
            if in_ul: html_parts.append("</ul>"); in_ul = False
            if in_ol: html_parts.append("</ol>"); in_ol = False
            if not in_quote:
                html_parts.append("<blockquote>"); in_quote = True
            html_parts.append(f"<p>{md_inline(stripped[2:])}</p>")
            continue
        if in_ul: html_parts.append("</ul>"); in_ul = False
        if in_ol: html_parts.append("</ol>"); in_ol = False
        if in_quote: html_parts.append("</blockquote>"); in_quote = False
        para_buf.append(stripped)
    flush_para()
    return "\n".join(html_parts)
    if in_ol: html_parts.append("</ol>")
    if in_quote: html_parts.append("</blockquote>")
    return "\n".join(html_parts)


SECTION_CLASS = {
    "场景": "sec-scene",
    "你的问题": "sec-question",
    "你的问题（先想再看）": "sec-question",
    "推演序列（每步先自己预测，再看下一步）": "sec-question",
    "推演序列": "sec-question",
    "揭示": "sec-reveal",
    "图": "sec-figure",
    "记住这一句": "sec-takeaway",
}


def render_card(card: dict) -> str:
    tid, icon, hint = TYPE_META.get(card.get("type", ""), (card.get("type"), "📄", ""))
    secs = card["sections"]
    out = [f'<section class="card" id="{card["id"]}">']
    out.append('<header class="card-head">')
    out.append(f'<span class="badge b-{card.get("type","")}">{icon} {tid}</span>')
    out.append(f'<span class="chapter">{md_inline(card.get("chapter",""))}</span>')
    out.append("</header>")
    out.append(f'<h2 class="card-title">{md_inline(card["title"])}</h2>')
    if hint:
        out.append(f'<p class="hint">{hint}</p>')
    for name, content in secs.items():
        cls = SECTION_CLASS.get(name, "")
        out.append(f'<div class="sec {cls}">')
        if cls not in ("sec-scene",):  # scene keeps no header for compactness
            label = name if name != "你的问题" else "停下来，先想你的答案"
            out.append(f'<div class="sec-label">{label}</div>')
        if name == "记住这一句":
            # content is a blockquote line
            m = re.search(r">\s*(.+)", content)
            text = m.group(1) if m else content
            out.append(f'<div class="takeaway">{md_inline(text)}</div>')
        else:
            out.append(render_section(name, content))
        out.append("</div>")
    out.append("</section>")
    return "\n".join(out)


def main():
    files = sorted(CARD_DIR.glob("*.md"))
    cards = []
    for f in files:
        if f.name == "README.md":
            continue
        cards.append(parse_card(f.read_text(encoding="utf-8")))
    cards.sort(key=lambda c: c["id"])
    cards_html = "\n".join(render_card(c) for c in cards)

    toc = "\n".join(
        f'<a class="toc-item t-{c["type"]}" href="#{c["id"]}">'
        f'<span class="toc-dot t-{c["type"]}"></span>{c["id"]} · {md_inline(c["title"])}</a>'
        for c in cards
    )

    page = TEMPLATE.replace("{{CARDS}}", cards_html).replace("{{TOC}}", toc)
    OUT.write_text(page, encoding="utf-8")
    print(f"OK: {len(cards)} cards -> {OUT}")


TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>DDIA 权衡卡 · 原型</title>
<script>
// mermaid CDN with localStorage cache fallback: load lazily only when needed
(function(){
  window.__mermaidReady = false;
  function load(src, cb){
    var s = document.createElement('script');
    s.src = src; s.onload = cb; s.onerror = function(){ /* offline: show source */ };
    document.head.appendChild(s);
  }
  window.initMermaid = function(){
    if (window.mermaid) {
      mermaid.initialize({ startOnLoad:false, theme:'neutral',
        flowchart:{ useMaxWidth:true, htmlLabels:true },
        themeVariables:{ fontSize:'13px' } });
      mermaid.run({ querySelector:'pre.mermaid' }).then(function(){ window.__mermaidReady = true; })
        .catch(function(e){ console.warn(e); });
    }
  };
  document.addEventListener('DOMContentLoaded', function(){
    // render on demand: first card containing mermaid
    var need = document.querySelector('pre.mermaid');
    if (need && !window.__mermaidLoaded) {
      window.__mermaidLoaded = true;
      load('https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js', window.initMermaid);
    }
  });
})();
</script>
<style>
:root{
  --bg:#f6f7f9; --card:#ffffff; --ink:#1c2330; --sub:#5b6472;
  --line:#e4e7ec; --accent:#2563eb;
  --dilemma:#2563eb; --simulation:#0d9488; --incident:#dc2626;
}
@media (prefers-color-scheme: dark){
  :root{ --bg:#10141b; --card:#171d27; --ink:#e7ebf2; --sub:#9aa4b2;
    --line:#2a3140; --accent:#60a5fa;
    --dilemma:#60a5fa; --simulation:#2dd4bf; --incident:#f87171; }
}
*{ box-sizing:border-box; }
body{ margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.75 -apple-system,"PingFang SC","Noto Sans SC",sans-serif; }
.wrap{ max-width:640px; margin:0 auto; padding:12px 14px 80px; }
.topbar{ position:sticky; top:0; z-index:5; background:var(--bg);
  padding:10px 0 8px; border-bottom:1px solid var(--line); margin-bottom:8px; }
.topbar h1{ font-size:17px; margin:0; }
.topbar .sub{ font-size:12px; color:var(--sub); }
details.tocbox{ border:1px solid var(--line); border-radius:10px;
  background:var(--card); margin:10px 0 18px; }
details.tocbox summary{ padding:10px 14px; cursor:pointer; font-weight:600; font-size:14px; }
.toc-item{ display:block; padding:7px 14px; border-top:1px solid var(--line);
  color:var(--ink); text-decoration:none; font-size:13.5px; line-height:1.5; }
.toc-dot{ display:inline-block; width:8px; height:8px; border-radius:50%;
  margin-right:8px; vertical-align:1px; }
.toc-dot.t-dilemma{ background:var(--dilemma); }
.toc-dot.t-simulation{ background:var(--simulation); }
.toc-dot.t-incident{ background:var(--incident); }

.card{ background:var(--card); border:1px solid var(--line); border-radius:14px;
  padding:18px 18px 14px; margin:18px 0; scroll-margin-top:70px; }
.card-head{ display:flex; align-items:center; justify-content:space-between; gap:8px; }
.badge{ font-size:12px; font-weight:700; padding:2px 9px; border-radius:99px; color:#fff; }
.b-dilemma{ background:var(--dilemma); }
.b-simulation{ background:var(--simulation); }
.b-incident{ background:var(--incident); }
.chapter{ font-size:12px; color:var(--sub); }
.card-title{ font-size:18px; margin:10px 0 2px; line-height:1.45; }
.hint{ font-size:12px; color:var(--sub); margin:0 0 6px; }
.sec{ margin-top:14px; }
.sec-label{ font-size:11.5px; font-weight:700; letter-spacing:.06em;
  color:var(--sub); text-transform:uppercase; margin-bottom:4px; }
.sec-scene{ border-left:3px solid var(--line); padding-left:12px; }
.sec-question{ background:color-mix(in srgb, var(--accent) 8%, transparent);
  border-radius:10px; padding:12px 14px; font-weight:500; }
.sec-reveal{ border-top:1px dashed var(--line); padding-top:10px; }
.sec-figure{ }
.takeaway{ margin-top:6px; padding:12px 14px; border-radius:10px;
  background:color-mix(in srgb, var(--dilemma) 12%, transparent);
  font-weight:600; line-height:1.7; }
blockquote{ margin:0 0 6px; padding-left:12px; border-left:3px solid var(--line);
  color:var(--sub); }
ul,ol{ margin:4px 0; padding-left:20px; }
li{ margin:5px 0; }
li > ul{ margin:2px 0 2px; }
code{ font-size:.9em; background:var(--line); border-radius:4px; padding:1px 5px;
  font-family:ui-monospace,Menlo,monospace; }
pre.code{ background:var(--bg); border:1px solid var(--line); border-radius:8px;
  padding:10px 12px; overflow-x:auto; font-size:12.5px; line-height:1.6; }
pre.code code{ background:none; padding:0; }
.mermaid-wrap{ margin:10px 0; padding:8px; border:1px solid var(--line);
  border-radius:10px; overflow-x:auto; text-align:center; }
pre.mermaid{ margin:0; display:flex; justify-content:center; }
.footnote{ text-align:center; color:var(--sub); font-size:12px; margin-top:30px; }
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <h1>DDIA 权衡卡 · 原型</h1>
    <div class="sub">第 5 章复制 + 第 7 章事务 · 15 张 · 手机可读</div>
  </div>
  <details class="tocbox">
    <summary>📋 卡片目录</summary>
    {{TOC}}
  </details>
{{CARDS}}
  <div class="footnote">原型 · 内容自包含 · mermaid 图首次联网加载后缓存</div>
</div>
</body>
</html>
"""

if __name__ == "__main__":
    sys.exit(main())
