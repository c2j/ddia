#!/usr/bin/env python3
"""把 prototype/ch5-cards/ 下的卡片 Markdown 渲染成单文件手机可读 HTML 原型。

用法：python3 build.py
输出：prototype/index.html（自包含，mermaid 走 CDN，首次在线加载后浏览器缓存）

功能：已读/未读标记、卡片内自测问答（对错即时反馈、答错计入复习）、收藏、进度统计。
用户状态存 localStorage。
"""
import html as htmllib
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
    parts = re.split(r"^## (.+)$", body, flags=re.M)
    sections = {}
    if parts[0].strip():
        sections["引言"] = parts[0].strip()
    for i in range(1, len(parts), 2):
        sections[parts[i].strip()] = parts[i + 1].strip()
    meta["sections"] = sections

    # optional quiz block: "## 自测" with items
    #   判断: 题干 [对/错]
    #   单选: 题干 | 选项A | 选项B* | 选项C   （* 标正确项）
    quizzes = []
    for q in re.finditer(
        r"^- (判断|单选|多选):\s*(.+)$", sections.get("自测", ""), flags=re.M
    ):
        kind, rest = q.group(1), q.group(2).strip()
        if kind == "判断":
            stem, ans = rest.rsplit("[", 1)
            quizzes.append({"kind": "judge", "stem": stem.strip(),
                            "answer": ans.rstrip("]").strip()})
        else:
            segs = [s.strip() for s in rest.split("|")]
            quizzes.append({"kind": "choice", "stem": segs[0],
                            "options": segs[1:]})
    meta["quiz"] = quizzes
    return meta


def md_inline(s: str) -> str:
    s = htmllib.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s, flags=re.S)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s, flags=re.S)
    return s


def render_section(content: str) -> str:
    blocks = []
    def stash(m):
        blocks.append((m.group(1) or "", m.group(2)))
        return f"\x00BLOCK{len(blocks)-1}\x00"

    content = re.sub(r"```(\w*)\n(.*?)```", stash, content, flags=re.S)

    html_parts = []
    in_ul = in_ol = in_quote = False
    para_buf = []

    def flush_para():
        nonlocal para_buf
        if para_buf:
            html_parts.append(f"<p>{md_inline(' '.join(para_buf))}</p>")
            para_buf = []

    def close_all():
        nonlocal in_ul, in_ol, in_quote
        if in_ul: html_parts.append("</ul>"); in_ul = False
        if in_ol: html_parts.append("</ol>"); in_ol = False
        if in_quote: html_parts.append("</blockquote>"); in_quote = False

    for raw in content.split("\n"):
        stripped = raw.strip()
        bm = re.match(r"^\s*\x00BLOCK(\d+)\x00\s*$", stripped)
        if bm:
            flush_para(); close_all()
            lang, body = blocks[int(bm.group(1))]
            if lang == "mermaid":
                html_parts.append(
                    f'<div class="mermaid-wrap"><pre class="mermaid">{body}</pre></div>')
            else:
                html_parts.append(
                    f'<pre class="code"><code>{htmllib.escape(body)}</code></pre>')
            continue
        if not stripped:
            flush_para(); close_all()
            continue
        if stripped.startswith("- "):
            flush_para()
            if in_quote: html_parts.append("</blockquote>"); in_quote = False
            if in_ol: html_parts.append("</ol>"); in_ol = False
            if not in_ul: html_parts.append("<ul>"); in_ul = True
            html_parts.append(f"<li>{md_inline(stripped[2:])}</li>")
            continue
        m_ol = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m_ol:
            flush_para()
            if in_quote: html_parts.append("</blockquote>"); in_quote = False
            if in_ul: html_parts.append("</ul>"); in_ul = False
            if not in_ol: html_parts.append("<ol>"); in_ol = True
            html_parts.append(f"<li>{md_inline(m_ol.group(2))}</li>")
            continue
        if stripped.startswith("> "):
            flush_para()
            close_lists = in_ul or in_ol
            if in_ul: html_parts.append("</ul>"); in_ul = False
            if in_ol: html_parts.append("</ol>"); in_ol = False
            if not in_quote: html_parts.append("<blockquote>"); in_quote = True
            html_parts.append(f"<p>{md_inline(stripped[2:])}</p>")
            continue
        flush_para(); close_all()
        para_buf.append(stripped)
    flush_para(); close_all()
    return "\n".join(html_parts)


SECTION_CLASS = {
    "场景": "sec-scene",
    "你的问题": "sec-question",
    "推演序列（每步先自己预测，再看下一步）": "sec-question",
    "推演序列": "sec-question",
    "揭示": "sec-reveal",
    "图": "sec-figure",
    "记住这一句": "sec-takeaway",
}


def render_quiz(card_id: str, quizzes: list) -> str:
    if not quizzes:
        return ""
    out = ['<div class="sec sec-quiz"><div class="sec-label">自测 · 巩固一下</div>']
    for qi, q in enumerate(quizzes):
        qid = f"{card_id}-q{qi}"
        if q["kind"] == "judge":
            correct = q["answer"].startswith("对") or q["answer"].lower() in ("true", "√")
            opts = [("对", correct), ("错", not correct)]
            out.append(f'<div class="quiz" data-qid="{qid}" data-kind="judge" data-correct="{str(correct).lower()}">')
            out.append(f'<div class="quiz-stem">{md_inline(q["stem"])}</div>')
            out.append('<div class="quiz-opts">')
            for text, _ in opts:
                out.append(f'<button class="quiz-opt" data-val="{text}">{text}</button>')
            out.append('</div><div class="quiz-fb"></div></div>')
        else:
            letters = "ABCDEF"
            correct_idx = next(i for i, o in enumerate(q["options"]) if o.endswith("*"))
            out.append(f'<div class="quiz" data-qid="{qid}" data-kind="choice" data-correct="{correct_idx}">')
            out.append(f'<div class="quiz-stem">{md_inline(q["stem"])}</div>')
            out.append('<div class="quiz-opts">')
            for i, o in enumerate(q["options"]):
                text = o.rstrip("*").strip()
                out.append(f'<button class="quiz-opt" data-val="{i}">{letters[i]}. {text}</button>')
            out.append('</div><div class="quiz-fb"></div></div>')
    out.append("</div>")
    return "\n".join(out)


def render_card(card: dict) -> str:
    tid, icon, hint = TYPE_META.get(card.get("type", ""), (card.get("type"), "📄", ""))
    secs = card["sections"]
    out = [f'<section class="card" id="{card["id"]}" data-cid="{card["id"]}">']
    out.append('<header class="card-head">')
    out.append(f'<span class="badge b-{card.get("type","")}">{icon} {tid}</span>')
    out.append(f'<span class="head-right">')
    out.append(f'<button class="star-btn" title="收藏">☆</button>')
    out.append(f'<span class="read-dot" title="学习状态"></span>')
    out.append(f'</span>')
    out.append("</header>")
    out.append(f'<h2 class="card-title">{md_inline(card["title"])}</h2>')
    if hint:
        out.append(f'<p class="hint">{hint}</p>')
    for name, content in secs.items():
        if name == "自测":
            continue
        cls = SECTION_CLASS.get(name, "")
        out.append(f'<div class="sec {cls}">')
        if cls != "sec-scene":
            label = "停下来，先想你的答案" if name == "你的问题" else name
            out.append(f'<div class="sec-label">{label}</div>')
        if name == "记住这一句":
            m = re.search(r">\s*(.+)", content)
            out.append(f'<div class="takeaway">{md_inline(m.group(1) if m else content)}</div>')
        else:
            out.append(render_section(content))
        out.append("</div>")
    out.append(render_quiz(card["id"], card["quiz"]))
    out.append(
        f'<footer class="card-foot">'
        f'<button class="mark-read-btn">✓ 标记为已学</button>'
        f"</footer>")
    out.append("</section>")
    return "\n".join(out)


def main():
    cards = []
    for f in sorted(CARD_DIR.glob("*.md")):
        if f.name == "README.md":
            continue
        cards.append(parse_card(f.read_text(encoding="utf-8")))
    cards.sort(key=lambda c: c["id"])
    cards_html = "\n".join(render_card(c) for c in cards)

    toc = "\n".join(
        f'<a class="toc-item t-{c["type"]}" href="#{c["id"]}" data-cid="{c["id"]}">'
        f'<span class="toc-dot t-{c["type"]}"></span>'
        f'<span class="toc-star" data-star="{c["id"]}"></span>'
        f'{md_inline(c["title"])}</a>'
        for c in cards
    )

    page = (TEMPLATE
            .replace("{{CARDS}}", cards_html)
            .replace("{{TOC}}", toc)
            .replace("{{COUNT}}", str(len(cards))))
    OUT.write_text(page, encoding="utf-8")
    print(f"OK: {len(cards)} cards -> {OUT}")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>DDIA 权衡卡 · 原型</title>
<script>
(function(){
  function load(src, cb){
    var s = document.createElement('script');
    s.src = src; s.onload = cb;
    s.onerror = function(){ document.body.classList.add('no-mermaid'); };
    document.head.appendChild(s);
  }
  document.addEventListener('DOMContentLoaded', function(){
    if (document.querySelector('pre.mermaid')) {
      load('https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js', function(){
        if (window.mermaid) {
          mermaid.initialize({ startOnLoad:false, theme:'neutral',
            flowchart:{ useMaxWidth:true, htmlLabels:true },
            themeVariables:{ fontSize:'13px' } });
          try { mermaid.run({ querySelector:'pre.mermaid' }); } catch(e){}
        }
      });
    }
  });
})();
</script>
<style>
:root{
  --bg:#f6f7f9; --card:#ffffff; --ink:#1c2330; --sub:#5b6472;
  --line:#e4e7ec; --accent:#2563eb; --ok:#16a34a; --bad:#dc2626;
  --star:#f59e0b;
  --dilemma:#2563eb; --simulation:#0d9488; --incident:#dc2626;
}
@media (prefers-color-scheme: dark){
  :root{ --bg:#10141b; --card:#171d27; --ink:#e7ebf2; --sub:#9aa4b2;
    --line:#2a3140; --accent:#60a5fa; --ok:#4ade80; --bad:#f87171; --star:#fbbf24;
    --dilemma:#60a5fa; --simulation:#2dd4bf; --incident:#f87171; }
}
*{ box-sizing:border-box; }
body{ margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.75 -apple-system,"PingFang SC","Noto Sans SC",sans-serif; }
.wrap{ max-width:640px; margin:0 auto; padding:12px 14px 120px; }

/* ---- top bar with progress ---- */
.topbar{ position:sticky; top:0; z-index:5; background:var(--bg);
  padding:10px 0 8px; border-bottom:1px solid var(--line); }
.topbar h1{ font-size:17px; margin:0; display:flex; justify-content:space-between; align-items:baseline;}
.topbar .progress-num{ font-size:13px; color:var(--accent); font-weight:700; }
.progress-bar{ height:4px; background:var(--line); border-radius:99px; margin-top:7px; overflow:hidden; }
.progress-fill{ height:100%; width:0%; background:var(--accent); border-radius:99px; transition:width .4s; }
.filter-row{ display:flex; gap:8px; margin-top:9px; flex-wrap:wrap; }
.chip{ font-size:12.5px; padding:4px 12px; border-radius:99px; border:1px solid var(--line);
  background:var(--card); color:var(--sub); cursor:pointer; user-select:none; }
.chip.on{ border-color:var(--accent); color:var(--accent); font-weight:700; }

details.tocbox{ border:1px solid var(--line); border-radius:10px;
  background:var(--card); margin:10px 0 18px; }
details.tocbox summary{ padding:10px 14px; cursor:pointer; font-weight:600; font-size:14px; }
.toc-item{ display:flex; align-items:center; gap:8px; padding:7px 14px;
  border-top:1px solid var(--line); color:var(--ink); text-decoration:none; font-size:13.5px; line-height:1.5; }
.toc-item.read .toc-title{ color:var(--sub); }
.toc-item.read .toc-title::after{ content:" ✓"; color:var(--ok); font-weight:700; }
.toc-dot{ flex:0 0 8px; width:8px; height:8px; border-radius:50%; }
.toc-dot.t-dilemma{ background:var(--dilemma); }
.toc-dot.t-simulation{ background:var(--simulation); }
.toc-dot.t-incident{ background:var(--incident); }
.toc-star{ flex:0 0 14px; text-align:center; color:var(--star); font-size:13px; }
.toc-star.empty{ visibility:hidden; }
.toc-title{ flex:1; }
.toc-item.starred .toc-title{ font-weight:600; }

/* ---- cards ---- */
.card{ background:var(--card); border:1px solid var(--line); border-radius:14px;
  padding:18px 18px 14px; margin:18px 0; scroll-margin-top:130px; transition:border-color .3s; }
.card.is-read{ border-color:color-mix(in srgb, var(--ok) 45%, var(--line)); }
.card.is-starred{ border-color:color-mix(in srgb, var(--star) 55%, var(--line)); }
.card-head{ display:flex; align-items:center; justify-content:space-between; gap:8px; }
.head-right{ display:flex; align-items:center; gap:10px; }
.badge{ font-size:12px; font-weight:700; padding:2px 9px; border-radius:99px; color:#fff; }
.b-dilemma{ background:var(--dilemma); }
.b-simulation{ background:var(--simulation); }
.b-incident{ background:var(--incident); }
.star-btn{ background:none; border:none; font-size:20px; color:var(--sub); cursor:pointer;
  padding:0 2px; line-height:1; }
.card.is-starred .star-btn{ color:var(--star); }
.read-dot{ width:9px; height:9px; border-radius:50%; background:var(--line); }
.card.is-read .read-dot{ background:var(--ok); }
.card-title{ font-size:18px; margin:10px 0 2px; line-height:1.45; }
.hint{ font-size:12px; color:var(--sub); margin:0 0 6px; }
.sec{ margin-top:14px; }
.sec-label{ font-size:11.5px; font-weight:700; letter-spacing:.06em;
  color:var(--sub); margin-bottom:4px; }
.sec-scene{ border-left:3px solid var(--line); padding-left:12px; }
.sec-question{ background:color-mix(in srgb, var(--accent) 8%, transparent);
  border-radius:10px; padding:12px 14px; font-weight:500; }
.sec-reveal{ border-top:1px dashed var(--line); padding-top:10px; }
.takeaway{ margin-top:6px; padding:12px 14px; border-radius:10px;
  background:color-mix(in srgb, var(--dilemma) 12%, transparent);
  font-weight:600; line-height:1.7; }
blockquote{ margin:0 0 6px; padding-left:12px; border-left:3px solid var(--line); color:var(--sub); }
ul,ol{ margin:4px 0; padding-left:20px; }
li{ margin:5px 0; }
code{ font-size:.9em; background:var(--line); border-radius:4px; padding:1px 5px;
  font-family:ui-monospace,Menlo,monospace; }
pre.code{ background:var(--bg); border:1px solid var(--line); border-radius:8px;
  padding:10px 12px; overflow-x:auto; font-size:12.5px; line-height:1.6; }
pre.code code{ background:none; padding:0; }
.mermaid-wrap{ margin:10px 0; padding:8px; border:1px solid var(--line);
  border-radius:10px; overflow-x:auto; text-align:center; }
pre.mermaid{ margin:0; display:flex; justify-content:center; }
.no-mermaid pre.mermaid{ white-space:pre-wrap; font-size:11px; color:var(--sub);
  text-align:left; font-family:ui-monospace,monospace; }

/* ---- quiz ---- */
.sec-quiz{ border-top:1px solid var(--line); padding-top:12px; }
.quiz{ margin:12px 0; padding:12px 14px; border:1px solid var(--line); border-radius:10px; }
.quiz-stem{ font-weight:600; margin-bottom:8px; line-height:1.6; }
.quiz-opts{ display:flex; gap:8px; flex-wrap:wrap; }
.quiz-opt{ flex:1 1 auto; min-width:72px; font-size:14px; padding:8px 12px;
  border:1px solid var(--line); border-radius:8px; background:var(--bg); color:var(--ink);
  cursor:pointer; transition:all .15s; font-family:inherit; line-height:1.5; text-align:left;}
.quiz-opt:active{ transform:scale(.97); }
.quiz.answered .quiz-opt{ cursor:default; opacity:.65; }
.quiz.answered .quiz-opt.picked{ opacity:1; }
.quiz.answered .quiz-opt.correct{ border-color:var(--ok); color:var(--ok); font-weight:700; opacity:1; }
.quiz.answered .quiz-opt.wrong{ border-color:var(--bad); color:var(--bad); font-weight:700; opacity:1; }
.quiz-fb{ display:none; margin-top:8px; font-size:13.5px; font-weight:600; }
.quiz.answered .quiz-fb{ display:block; }
.quiz.right .quiz-fb{ color:var(--ok); }
.quiz.wrongq .quiz-fb{ color:var(--bad); }

/* ---- footer buttons ---- */
.card-foot{ margin-top:16px; padding-top:12px; border-top:1px solid var(--line);
  display:flex; justify-content:flex-end; }
.mark-read-btn{ font-size:13.5px; font-weight:600; padding:8px 16px; border-radius:99px;
  border:1.5px solid var(--accent); background:transparent; color:var(--accent); cursor:pointer;
  font-family:inherit; }
.card.is-read .mark-read-btn{ border-color:var(--ok); color:var(--ok); }

/* ---- bottom nav ---- */
.bottom-nav{ position:fixed; bottom:0; left:0; right:0; z-index:6;
  background:color-mix(in srgb, var(--card) 92%, transparent);
  -webkit-backdrop-filter:blur(10px); backdrop-filter:blur(10px);
  border-top:1px solid var(--line); display:flex; }
.bottom-nav button{ flex:1; background:none; border:none; padding:12px 4px 20px;
  font-size:12.5px; color:var(--sub); cursor:pointer; font-family:inherit; }
.bottom-nav button.on{ color:var(--accent); font-weight:700; }
.bottom-nav button .cnt{ display:block; font-size:15px; font-weight:800; }
.hidden{ display:none !important; }
.footnote{ text-align:center; color:var(--sub); font-size:12px; margin-top:30px; }
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <h1>DDIA 权衡卡 · 原型 <span class="progress-num" id="prog-num">0/{{COUNT}}</span></h1>
    <div class="progress-bar"><div class="progress-fill" id="prog-fill"></div></div>
    <div class="filter-row" id="filters">
      <button class="chip on" data-filter="all">全部</button>
      <button class="chip" data-filter="unread">未学</button>
      <button class="chip" data-filter="starred">★ 收藏</button>
      <button class="chip" data-filter="quiz-wrong">答错过</button>
    </div>
  </div>
  <details class="tocbox">
    <summary>📋 卡片目录</summary>
    {{TOC}}
  </details>
{{CARDS}}
  <div class="footnote">原型 · 状态保存在本机浏览器 · 清除浏览器数据会重置进度</div>
</div>
<nav class="bottom-nav">
  <button id="nav-all" class="on">全部<span class="cnt">{{COUNT}}</span></button>
  <button id="nav-unread">未学<span class="cnt" id="cnt-unread">{{COUNT}}</span></button>
  <button id="nav-starred">收藏<span class="cnt" id="cnt-starred">0</span></button>
</nav>
<script>
(function(){
  var LS = 'ddia-cards-v1';
  var state = { read:{}, starred:{}, quizWrong:{} };
  try { state = Object.assign(state, JSON.parse(localStorage.getItem(LS) || '{}')); } catch(e){}
  function save(){ localStorage.setItem(LS, JSON.stringify(state)); }

  var cards = Array.prototype.slice.call(document.querySelectorAll('.card'));
  var tocItems = {};
  document.querySelectorAll('.toc-item').forEach(function(a){ tocItems[a.dataset.cid] = a; });

  function refreshCard(el){
    var cid = el.dataset.cid;
    el.classList.toggle('is-read', !!state.read[cid]);
    el.classList.toggle('is-starred', !!state.starred[cid]);
    el.querySelector('.mark-read-btn').textContent = state.read[cid] ? '✓ 已学（点击取消）' : '✓ 标记为已学';
    el.querySelector('.star-btn').textContent = state.starred[cid] ? '★' : '☆';
    var t = tocItems[cid];
    if (t) {
      t.classList.toggle('read', !!state.read[cid]);
      t.classList.toggle('starred', !!state.starred[cid]);
      var s = t.querySelector('.toc-star');
      s.textContent = '★';
      s.classList.toggle('empty', !state.starred[cid]);
    }
  }
  function refreshProgress(){
    var total = cards.length;
    var n = cards.filter(function(c){ return state.read[c.dataset.cid]; }).length;
    var ns = cards.filter(function(c){ return state.starred[c.dataset.cid]; }).length;
    document.getElementById('prog-num').textContent = n + '/' + total;
    document.getElementById('prog-fill').style.width = (total ? 100*n/total : 0) + '%';
    document.getElementById('cnt-unread').textContent = total - n;
    document.getElementById('cnt-starred').textContent = ns;
    document.getElementById('nav-all').querySelector('.cnt').textContent = total;
  }
  function applyFilter(mode){
    cards.forEach(function(c){
      var cid = c.dataset.cid, show = true;
      if (mode === 'unread') show = !state.read[cid];
      else if (mode === 'starred') show = !!state.starred[cid];
      else if (mode === 'quiz-wrong') show = !!state.quizWrong[cid];
      c.classList.toggle('hidden', !show);
    });
    document.querySelectorAll('#filters .chip').forEach(function(ch){
      ch.classList.toggle('on', ch.dataset.filter === mode);
    });
    ['all','unread','starred'].forEach(function(id){
      document.getElementById('nav-' + id).classList.toggle('on', id === mode);
    });
    window.scrollTo(0,0);
  }

  cards.forEach(function(c){
    var cid = c.dataset.cid;
    c.querySelector('.star-btn').addEventListener('click', function(){
      state.starred[cid] = !state.starred[cid];
      if (!state.starred[cid]) delete state.starred[cid];
      save(); refreshCard(c); refreshProgress();
    });
    c.querySelector('.mark-read-btn').addEventListener('click', function(){
      state.read[cid] = !state.read[cid];
      if (!state.read[cid]) delete state.read[cid];
      save(); refreshCard(c); refreshProgress();
    });
    // quiz interaction
    c.querySelectorAll('.quiz').forEach(function(qz){
      var correct = qz.dataset.correct;
      var isJudge = qz.dataset.kind === 'judge';
      qz.querySelectorAll('.quiz-opt').forEach(function(btn){
        btn.addEventListener('click', function(){
          if (qz.classList.contains('answered')) return;
          var picked = btn.dataset.val;
          var ok = String(picked) === String(correct);
          qz.classList.add('answered', ok ? 'right' : 'wrongq');
          btn.classList.add('picked', ok ? 'correct' : 'wrong');
          if (!ok) {
            var cbtn = Array.prototype.find.call(qz.querySelectorAll('.quiz-opt'),
              function(b){ return String(b.dataset.val) === String(correct); });
            if (cbtn) cbtn.classList.add('correct');
          }
          var fb = qz.querySelector('.quiz-fb');
          fb.textContent = ok ? '✓ 答对了' : '✗ 答错了，正确的已标出';
          // record wrong for review filter
          var hadWrong = state.quizWrong[cid];
          if (!ok && !hadWrong) { state.quizWrong[cid] = true; save(); }
          if (ok && hadWrong) {
            // only clear if all quizzes in card answered correctly at least once
            var allOk = Array.prototype.every.call(c.querySelectorAll('.quiz'), function(q2){
              return q2 === qz ? ok : q2.classList.contains('right');
            });
            if (allOk) { delete state.quizWrong[cid]; save(); }
          }
          refreshCard(c);
        });
      });
    });
    refreshCard(c);
  });

  document.querySelectorAll('#filters .chip').forEach(function(ch){
    ch.addEventListener('click', function(){ applyFilter(ch.dataset.filter); });
  });
  ['all','unread','starred'].forEach(function(id){
    document.getElementById('nav-' + id).addEventListener('click', function(){ applyFilter(id); });
  });

  refreshProgress();
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    sys.exit(main())
