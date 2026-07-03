#!/usr/bin/env python3
"""
GMATWiz lesson authoring + build script.

Authors the GMAT Focus Quant (Problem Solving) lesson content as Python data
(the single source of truth below), then emits, ONLY inside this folder:

  - <slug>.json            one structured lesson file per topic (consumes -> app)
  - index.json             manifest of all topics + file paths
  - README                 plain-text coverage + pedagogical model summary
  - html/<slug>.html       self-contained, Tufte-clean review page per topic
  - html/index.html        a simple hub linking every topic page

Pedagogical model (grounded in PRD Section 2 + Section 9 and the two skills):
  - Retrieval-practice opening  (Rosenshine P1; Ausubel advance organiser; Agarwal)
  - I do  -> we do -> you do    (worked example -> guided -> independent; Archer)
  - Application-first (SPOV2):  you_do explanations are revealed AFTER an attempt
  - Mastery = >=85% on new/held-out items across >=2 spaced sessions (PRD 9)

This script does not touch anything outside gmatwiz/lessons/.
Run:  python3 build.py
"""

import html as _html
import json
import os
import re

SCHEMA_VERSION = "1.0"
EXAM = "GMAT Focus Edition"
SECTION = "Quantitative Reasoning"
QTYPE = "Problem Solving"
AUTHORED_SOURCE = "GMATWiz authored"
HERE = os.path.dirname(os.path.abspath(__file__))
HTML_DIR = os.path.join(HERE, "html")

ALL_ERROR_TYPES = ["content gap", "reasoning flaw", "timing", "careless", "trap"]

# Standard mastery-check conditions (PRD Section 9.2 + Section 4 thresholds).
MASTERY_CONDITIONS = [
    ">=85% correct on new/held-out-style items (not flashcard recall) per session",
    "sustained across >=2 spaced sessions with a delay between them",
    "per-topic memory surfaced only after >=20 graded reviews (PRD give-up rule)",
    "per-topic performance surfaced only after >=8 application attempts (PRD give-up rule)",
]
MASTERY_DEFINITION = (
    "A topic is mastered at >=85% correct on new/held-out-style questions across "
    ">=2 spaced sessions with delay (PRD Section 9.2). Flashcard recall alone is not "
    "mastery; application under mixed, delayed conditions is the bar."
)
MASTERY_ON_FAIL = (
    "Not yet: route every miss to the required error log (tag why: content gap / "
    "reasoning flaw / timing / careless / trap), schedule spaced re-practice via "
    "topic-aware scheduling, then re-enter the we-do -> you-do loop before re-testing."
)


# ---------------------------------------------------------------------------
# CONTENT: the 18 GMAT Focus Quant leaf topics (PRD Section 5).
# Authored in topics_data.py (the content source of truth).
# ---------------------------------------------------------------------------
from topics_data import TOPICS  # noqa: E402


# ---------------------------------------------------------------------------
# finalize: stamp shared fields onto every item so each is import-ready.
# ---------------------------------------------------------------------------
def all_items(t):
    items = [t["i_do"]] + t["we_do"] + t["you_do"]
    items += t.get("mastery_check", {}).get("sample_held_out_items", [])
    return items


def finalize(t):
    t.setdefault("schema_version", SCHEMA_VERSION)
    t.setdefault("section", SECTION)
    t.setdefault("question_type", QTYPE)
    t.setdefault("exam", EXAM)
    t["mastery_check"].setdefault("definition", MASTERY_DEFINITION)
    t["mastery_check"].setdefault("threshold", 0.85)
    t["mastery_check"].setdefault("min_spaced_sessions", 2)
    t["mastery_check"].setdefault("conditions", MASTERY_CONDITIONS)
    t["mastery_check"].setdefault("on_fail", MASTERY_ON_FAIL)
    for it in all_items(t):
        it["topic"] = t["topic_id"]
        it.setdefault("source", AUTHORED_SOURCE)
        it.setdefault("official_flag", False)
        it.setdefault("question_type", QTYPE)
    # you_do is application-first: explanation revealed only after an attempt.
    for it in t["you_do"]:
        it["reveal_explanation_after_attempt"] = True
        it.setdefault("error_log_error_types", ALL_ERROR_TYPES)
    return t


# ---------------------------------------------------------------------------
# HTML rendering (self-contained, Tufte-clean).
# ---------------------------------------------------------------------------
CSS = """
:root{
  --ink:#1a1813; --muted:#6b6358; --rule:#d9d2c5; --bg:#fbf9f4; --card:#fffdf8;
  --accent:#7a3b2e; --accent2:#3a5a40; --link:#7a3b2e; --code:#2b2b2b;
}
*{box-sizing:border-box}
html{font-size:17px}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font-family:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
  line-height:1.55; -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1180px; margin:0 auto; padding:3rem 2rem 6rem;}
.content{max-width:720px;}
header.masthead{border-bottom:1px solid var(--rule); padding-bottom:1.2rem; margin-bottom:2rem;}
.kicker{font-size:.72rem; letter-spacing:.18em; text-transform:uppercase; color:var(--muted); margin:0 0 .4rem;}
h1{font-size:2.3rem; line-height:1.1; margin:.1rem 0 .6rem; font-weight:600; letter-spacing:-.01em;}
.meta{color:var(--muted); font-size:.9rem; margin:0;}
.meta b{color:var(--ink); font-weight:600;}
h2{font-size:1.45rem; margin:2.8rem 0 .3rem; font-weight:600; letter-spacing:-.01em;}
h2 .num{color:var(--accent); font-variant-numeric:tabular-nums; margin-right:.5rem;}
h3{font-size:1.06rem; margin:1.6rem 0 .4rem; font-weight:600;}
.sub{color:var(--muted); font-style:italic; margin:.1rem 0 1rem; font-size:.95rem;}
p{margin:.6rem 0;} ul,ol{margin:.5rem 0 .9rem; padding-left:1.3rem;} li{margin:.25rem 0;}
a{color:var(--link); text-decoration:none; border-bottom:1px solid rgba(122,59,46,.35);}
a:hover{border-bottom-color:var(--link);}
.lead{font-size:1.08rem;}
section{position:relative;}
.note{font-size:.8rem; color:var(--muted); line-height:1.4;}
.objectives{background:var(--card); border:1px solid var(--rule); border-radius:8px; padding:1rem 1.2rem;}
.objectives ul{margin:.3rem 0 0;}
.intent{border-left:3px solid var(--accent2); padding:.4rem 0 .4rem 1rem; margin:1rem 0; font-size:1.05rem;}
.donow{background:#2b2620; color:#f3ecde; border-radius:8px; padding:1.1rem 1.3rem; margin:1rem 0;}
.donow .tag{font-size:.7rem; letter-spacing:.16em; text-transform:uppercase; color:#d8b48a;}
.donow ol{padding-left:1.2rem;} .donow li{margin:.4rem 0;}
.donow .ans{color:#b9c6a9; font-style:italic; font-size:.86rem; display:block; margin-top:.15rem;}
table{border-collapse:collapse; width:100%; font-size:.92rem; margin:.6rem 0 1rem;}
th,td{text-align:left; padding:.45rem .6rem; border-bottom:1px solid var(--rule); vertical-align:top;}
th{font-size:.74rem; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); font-weight:600;}
td.t{white-space:nowrap; color:var(--accent); font-variant-numeric:tabular-nums; width:6.5rem;}
.q{background:var(--card); border:1px solid var(--rule); border-radius:8px; padding:1.1rem 1.3rem; margin:1.1rem 0;}
.q .qid{font-size:.72rem; letter-spacing:.12em; text-transform:uppercase; color:var(--muted);}
.q .qid .diff{float:right; color:var(--accent2);}
.q .stem{font-size:1.03rem; margin:.35rem 0 .6rem;}
.choices{list-style:none; padding:0; margin:.2rem 0 .4rem; counter-reset:c;}
.choices li{padding:.32rem .6rem; border:1px solid var(--rule); border-radius:6px; margin:.3rem 0; background:#fff;}
.choices li .lab{display:inline-block; width:1.5rem; font-weight:600; color:var(--accent);}
.choices li.correct{border-color:var(--accent2); background:#eef3ec;}
.choices li.correct .lab{color:var(--accent2);}
details{margin:.5rem 0 .2rem; border-top:1px dashed var(--rule); padding-top:.5rem;}
details>summary{cursor:pointer; font-size:.86rem; color:var(--accent); font-weight:600; list-style:none;}
details>summary::-webkit-details-marker{display:none;}
details>summary::before{content:"\\25B8  "; color:var(--accent);}
details[open]>summary::before{content:"\\25BE  ";}
.expl{font-size:.95rem; margin-top:.5rem;}
.hints{font-size:.92rem;} .hints li{margin:.2rem 0;}
.feedback{font-size:.9rem;} .feedback .ok{color:var(--accent2);} .feedback .no{color:var(--accent);}
.appfirst{font-size:.78rem; color:var(--accent); text-transform:uppercase; letter-spacing:.1em; margin:.2rem 0;}
.mastery{background:var(--card); border:1px solid var(--rule); border-left:3px solid var(--accent2); border-radius:8px; padding:1rem 1.2rem;}
.pill{display:inline-block; font-size:.72rem; padding:.12rem .5rem; border:1px solid var(--rule); border-radius:999px; color:var(--muted); margin:.1rem .2rem .1rem 0;}
footer{margin-top:3.5rem; border-top:1px solid var(--rule); padding-top:1rem; color:var(--muted); font-size:.82rem;}
.src{background:#eef3ec; border:1px solid #cfe0cf; border-radius:8px; padding:.9rem 1.1rem; margin:1.2rem 0;}
.src .tag{font-size:.7rem; letter-spacing:.14em; text-transform:uppercase; color:var(--accent2); font-weight:600;}
.crumbs{font-size:.85rem; margin-bottom:1.2rem;}
.ask{font-size:.9rem; background:#fff8ec; border:1px dashed #e0c590; border-radius:8px; padding:.7rem 1rem; margin:1.4rem 0;}
@media print{ body{background:#fff} .wrap{padding:0} a{border:none} .donow{-webkit-print-color-adjust:exact; print-color-adjust:exact} }
"""


def esc(s):
    return _html.escape(str(s), quote=True)


def render_choices(it):
    rows = []
    for L in ["A", "B", "C", "D", "E"]:
        cls = " class=\"correct\"" if L == it["correct"] else ""
        rows.append(
            f'<li{cls}><span class="lab">{L}</span>{esc(it["options"][L])}</li>'
        )
    return '<ul class="choices">' + "".join(rows) + "</ul>"


def render_ido(it):
    steps = "".join(f"<li>{esc(s)}</li>" for s in it.get("think_aloud_steps", []))
    return f"""
    <div class="q">
      <div class="qid">I DO &middot; worked example<span class="diff">{esc(it['difficulty'])}</span></div>
      <div class="stem">{esc(it['stem'])}</div>
      {render_choices(it)}
      <h3>Think-aloud</h3>
      <ol>{steps}</ol>
      <p class="expl"><b>Correct: {it['correct']}.</b> {esc(it['explanation'])}</p>
      <p class="note"><b>Takeaway.</b> {esc(it.get('key_takeaway',''))}</p>
    </div>"""


def render_wedo(it):
    hints = "".join(f"<li>{esc(h)}</li>" for h in it.get("scaffold_hints", []))
    fb = it.get("immediate_feedback", {})
    return f"""
    <div class="q">
      <div class="qid">{esc(it['id'])} &middot; we do (guided)<span class="diff">{esc(it['difficulty'])}</span></div>
      <div class="stem">{esc(it['stem'])}</div>
      {render_choices(it)}
      <details><summary>Scaffold hints (peek only if stuck)</summary>
        <ol class="hints">{hints}</ol>
      </details>
      <details><summary>Immediate feedback &amp; explanation</summary>
        <p class="feedback"><span class="ok">If correct:</span> {esc(fb.get('if_correct',''))}<br>
        <span class="no">If incorrect:</span> {esc(fb.get('if_incorrect',''))}</p>
        <p class="expl"><b>Answer: {it['correct']}.</b> {esc(it['explanation'])}</p>
      </details>
    </div>"""


def render_youdo(it, kind="you do (independent)"):
    types = it.get("error_log_error_types", [])
    et = "".join(f'<span class="pill">{esc(x)}</span>' for x in types)
    log_line = f'<p class="note">If you missed it, log it: {et}</p>' if types else ""
    secs = it.get("target_seconds")
    pace = f' &middot; target {secs}s' if secs else ""
    return f"""
    <div class="q">
      <div class="qid">{esc(it['id'])} &middot; {kind}{pace}<span class="diff">{esc(it['difficulty'])}</span></div>
      <p class="appfirst">Application-first &mdash; attempt before revealing</p>
      <div class="stem">{esc(it['stem'])}</div>
      {render_choices(it)}
      <details><summary>Reveal explanation (after your attempt)</summary>
        <p class="expl"><b>Answer: {it['correct']}.</b> {esc(it['explanation'])}</p>
        {log_line}
      </details>
    </div>"""


def render_opening(op):
    do = op["do_now"]
    items = "".join(
        f'<li>{esc(i["prompt"])}<span class="ans">{esc(i["answer"])}</span></li>'
        for i in do["items"]
    )
    crit = "".join(f"<li>{esc(c)}</li>" for c in op["success_criteria"])
    script = "".join(
        f'<tr><td class="t">{esc(s["time"])}</td><td>{esc(s["move"])}</td></tr>'
        for s in op["opening_script"]
    )
    rs = op.get("retrieval_starter", {})
    return f"""
    <section>
      <h2><span class="num">1</span>Opening &mdash; retrieval &amp; bridge</h2>
      <p class="sub">Builds on: {esc(op['builds_on'])}</p>
      <div class="donow">
        <div class="tag">Do Now &middot; from memory, no notes</div>
        <p>{esc(do['instructions'])}</p>
        <ol>{items}</ol>
      </div>
      <p class="note"><b>Retrieval starter ({esc(rs.get('duration_minutes','5'))} min).</b> {esc(rs.get('purpose',''))}
      <br><b>If students struggle:</b> {esc(rs.get('if_students_struggle',''))}</p>
      <h3>Prior-knowledge bridge</h3>
      <p>{esc(op['prior_knowledge_bridge'])}</p>
      <h3>Learning intention</h3>
      <p class="intent">{esc(op['learning_intention'])}</p>
      <p class="note"><b>You'll know you've got it when:</b></p>
      <ul>{crit}</ul>
      <details><summary>Complete timed opening script</summary>
        <table><thead><tr><th>Time</th><th>Move</th></tr></thead><tbody>{script}</tbody></table>
      </details>
    </section>"""


def render_mastery(mc):
    cond = "".join(f"<li>{esc(c)}</li>" for c in mc["conditions"])
    samples = ""
    if mc.get("sample_held_out_items"):
        samples = "<h3>Sample held-out check items</h3>" + "".join(
            render_youdo(s, kind="held-out check") for s in mc["sample_held_out_items"]
        )
    return f"""
    <section>
      <h2><span class="num">5</span>Mastery check</h2>
      <div class="mastery">
        <p>{esc(mc['definition'])}</p>
        <p class="note"><b>Threshold</b> {esc(mc['threshold'])} &middot; <b>spaced sessions</b> &ge; {esc(mc['min_spaced_sessions'])}</p>
        <ul>{cond}</ul>
        <p class="note"><b>If not yet mastered:</b> {esc(mc['on_fail'])}</p>
      </div>
      {samples}
    </section>"""


def primary_citation(t):
    for c in t["citations"]:
        if c.get("primary"):
            return c
    return t["citations"][0]


def render_html(t):
    we = "".join(render_wedo(x) for x in t["we_do"])
    you = "".join(render_youdo(x) for x in t["you_do"])
    obj = "".join(f"<li>{esc(o)}</li>" for o in t["learning_objectives"])
    pre = ", ".join(esc(p) for p in t["prerequisites"]) or "none"
    pc = primary_citation(t)
    other = "".join(
        f'<li><a href="{esc(c["url"])}">{esc(c["name"])}</a>'
        + (f' &mdash; {esc(c["note"])}' if c.get("note") else "")
        + "</li>"
        for c in t["citations"]
        if c is not pc
    )
    other_block = f"<p class='note'>Further reading:</p><ul>{other}</ul>" if other else ""
    pm = t["pedagogical_model"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(t['title'])} &middot; GMATWiz Quant</title>
<style>{CSS}</style></head>
<body><div class="wrap"><div class="content">
  <div class="crumbs"><a href="index.html">&larr; All Quant topics</a> &middot; {esc(t['domain'])}</div>
  <header class="masthead">
    <p class="kicker">GMATWiz &middot; {esc(t['exam'])} &middot; {esc(t['section'])} ({esc(t['question_type'])})</p>
    <h1>{esc(t['title'])}</h1>
    <p class="meta"><b>Topic id</b> <code>{esc(t['topic_id'])}</code> &middot; <b>Domain</b> {esc(t['domain'])}
      &middot; <b>Prereqs</b> {pre} &middot; <b>~{esc(t.get('estimated_minutes','20'))} min</b></p>
  </header>

  <div class="objectives">
    <p class="note"><b>Learning objectives</b></p>
    <ul>{obj}</ul>
    <p class="note">Model: {esc(pm['sequence'])} &middot; application-first (explanations revealed after an attempt) &middot; {esc(', '.join(pm['frameworks']))}.</p>
  </div>

  {render_opening(t['opening'])}

  <section>
    <h2><span class="num">2</span>I do &mdash; worked example</h2>
    <p class="sub">Watch the reasoning modeled end to end before you try.</p>
    {render_ido(t['i_do'])}
  </section>

  <section>
    <h2><span class="num">3</span>We do &mdash; guided practice</h2>
    <p class="sub">Scaffolds and immediate feedback are one click away. Fade them as you gain confidence.</p>
    {we}
  </section>

  <section>
    <h2><span class="num">4</span>You do &mdash; independent application</h2>
    <p class="sub">Application-first (SPOV2): commit to an answer, then reveal the explanation. Log every miss.</p>
    {you}
  </section>

  {render_mastery(t['mastery_check'])}

  <div class="src">
    <div class="tag">Primary source</div>
    <p><a href="{esc(pc['url'])}">{esc(pc['name'])}</a>{(' &mdash; ' + esc(pc['note'])) if pc.get('note') else ''}</p>
    {other_block}
  </div>

  <div class="ask">Stuck on any step? Ask your GMATWiz coach for a worked walkthrough &mdash; that's what it's here for.</div>

  <footer>
    <p>GMATWiz lesson &middot; <code>{esc(t['slug'])}.json</code> &middot; schema v{esc(t['schema_version'])} &middot; authored content (OfficialFlag=false), reserved official items used only for late checkpoints.</p>
  </footer>
</div></div></body></html>"""


def render_hub(topics):
    by_domain = {}
    for t in topics:
        by_domain.setdefault(t["domain"], []).append(t)
    blocks = ""
    for dom in ["Arithmetic", "Algebra"]:
        rows = "".join(
            f'<tr><td><a href="{esc(t["slug"])}.html">{esc(t["title"])}</a></td>'
            f'<td><code>{esc(t["topic_id"])}</code></td>'
            f'<td>{len(t["we_do"])} we &middot; {len(t["you_do"])} you</td></tr>'
            for t in by_domain.get(dom, [])
        )
        blocks += f"<h2>{esc(dom)}</h2><table><thead><tr><th>Topic</th><th>Topic id</th><th>Items</th></tr></thead><tbody>{rows}</tbody></table>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GMATWiz &middot; Quant Problem Solving lessons</title>
<style>{CSS}</style></head>
<body><div class="wrap"><div class="content">
  <header class="masthead">
    <p class="kicker">GMATWiz &middot; {esc(EXAM)} &middot; {esc(SECTION)}</p>
    <h1>Quant Problem Solving &mdash; lesson library</h1>
    <p class="meta">{len(topics)} leaf topics &middot; retrieval opening &rarr; I-do / we-do / you-do &rarr; mastery check &middot; application-first (SPOV2).</p>
  </header>
  <p class="lead">Each lesson opens with a low-stakes retrieval starter, models one worked example, fades support through guided practice, then puts you on new exam-style items where the explanation is withheld until you commit to an answer.</p>
  {blocks}
  <footer><p>Authored for learning. Official questions are reserved as late-stage checkpoints (PRD Section 13).</p></footer>
</div></div></body></html>"""


# ---------------------------------------------------------------------------
# SCHEMA VALIDATION (stdlib-only; validates generated JSON against schema.json).
# Supports the JSON-Schema draft-07 subset actually used by schema.json:
# type, required, properties, items, enum, pattern, minItems, maxItems,
# allOf, $ref (local), and additionalProperties.
# ---------------------------------------------------------------------------
def _type_ok(inst, t):
    if t == "object":
        return isinstance(inst, dict)
    if t == "array":
        return isinstance(inst, list)
    if t == "string":
        return isinstance(inst, str)
    if t == "integer":
        return isinstance(inst, int) and not isinstance(inst, bool)
    if t == "number":
        return isinstance(inst, (int, float)) and not isinstance(inst, bool)
    if t == "boolean":
        return isinstance(inst, bool)
    if t == "null":
        return inst is None
    return True


def _resolve_ref(ref, root):
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported $ref: {ref}")
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def _validate(inst, schema, root, path, errors):
    if not isinstance(schema, dict):
        return
    if "$ref" in schema:
        _validate(inst, _resolve_ref(schema["$ref"], root), root, path, errors)
    for sub in schema.get("allOf", []):
        _validate(inst, sub, root, path, errors)
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(inst, t) for t in types):
            errors.append(f"{path}: expected type {schema['type']}, got {type(inst).__name__}")
            return
    if "enum" in schema and inst not in schema["enum"]:
        errors.append(f"{path}: {inst!r} not in enum {schema['enum']}")
    if "pattern" in schema and isinstance(inst, str):
        if re.search(schema["pattern"], inst) is None:
            errors.append(f"{path}: {inst!r} does not match pattern {schema['pattern']!r}")
    if isinstance(inst, dict):
        props = schema.get("properties", {})
        for req in schema.get("required", []):
            if req not in inst:
                errors.append(f"{path}: missing required key '{req}'")
        if schema.get("additionalProperties", True) is False:
            for k in inst:
                if k not in props:
                    errors.append(f"{path}: additional property '{k}' not allowed")
        for k, subschema in props.items():
            if k in inst:
                _validate(inst[k], subschema, root, f"{path}.{k}", errors)
    if isinstance(inst, list):
        if "minItems" in schema and len(inst) < schema["minItems"]:
            errors.append(f"{path}: array len {len(inst)} < minItems {schema['minItems']}")
        if "maxItems" in schema and len(inst) > schema["maxItems"]:
            errors.append(f"{path}: array len {len(inst)} > maxItems {schema['maxItems']}")
        if isinstance(schema.get("items"), dict):
            for i, el in enumerate(inst):
                _validate(el, schema["items"], root, f"{path}[{i}]", errors)


def validate_against_schema(data_by_slug):
    """Validate each already-written lesson JSON against schema.json on disk."""
    with open(os.path.join(HERE, "schema.json"), encoding="utf-8") as f:
        schema = json.load(f)
    errors = []
    for slug, data in data_by_slug.items():
        _validate(data, schema, schema, slug, errors)
    return errors


# ---------------------------------------------------------------------------
# WRITE EVERYTHING
# ---------------------------------------------------------------------------
def check_items(topics):
    """Integrity checks: option letters, answer key validity, no duplicate
    distractor values, and we_do/you_do counts. Returns a list of problems."""
    problems = []
    for t in topics:
        we, you = len(t["we_do"]), len(t["you_do"])
        if not (2 <= we <= 3):
            problems.append(f"{t['slug']}: we_do has {we} (need 2-3)")
        if not (3 <= you <= 5):
            problems.append(f"{t['slug']}: you_do has {you} (need 3-5)")
        ids = []
        for it in all_items(t):
            ids.append(it["id"])
            keys = sorted(it["options"].keys())
            if keys != ["A", "B", "C", "D", "E"]:
                problems.append(f"{t['slug']}/{it['id']}: options keys {keys}")
            if it["correct"] not in it["options"]:
                problems.append(f"{t['slug']}/{it['id']}: correct {it['correct']} not an option")
            vals = [str(v).strip() for v in it["options"].values()]
            if len(set(vals)) != len(vals):
                dup = sorted({v for v in vals if vals.count(v) > 1})
                problems.append(f"{t['slug']}/{it['id']}: duplicate option value(s) {dup}")
        if len(set(ids)) != len(ids):
            problems.append(f"{t['slug']}: duplicate item id(s)")
    return problems


def build():
    topics = [finalize(t) for t in TOPICS]
    slugs = [t["slug"] for t in topics]
    assert len(slugs) == len(set(slugs)), "duplicate slug!"

    problems = check_items(topics)
    if problems:
        print("INTEGRITY PROBLEMS:")
        for p in problems:
            print("  - " + p)
        raise SystemExit(1)

    os.makedirs(HTML_DIR, exist_ok=True)

    # per-topic JSON
    for t in topics:
        path = os.path.join(HERE, t["slug"] + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(t, f, ensure_ascii=False, indent=2)
            f.write("\n")

    # index.json
    index = {
        "schema_version": SCHEMA_VERSION,
        "exam": EXAM,
        "section": SECTION,
        "question_type": QTYPE,
        "generated_by": "gmatwiz/lessons/build.py",
        "schema_file": "schema.json",
        "pedagogical_model": {
            "opening": "retrieval practice (Rosenshine P1; Ausubel; Agarwal)",
            "loop": "I do -> we do -> you do (Archer; PRD Section 9)",
            "application_first": "SPOV2 toggle: you_do explanations revealed after attempt",
            "mastery": ">=85% on new items across >=2 spaced sessions (PRD Section 9.2)",
        },
        "notetype_mapping": {
            "note": "Each practice item maps onto the PRD Section 8 'GMAT PS' notetype.",
            "Stem": "item.stem",
            "OptionA..OptionE": "item.options.A .. item.options.E",
            "Correct": "item.correct",
            "Explanation": "item.explanation",
            "Topic": "item.topic",
            "Difficulty": "item.difficulty",
            "Source": "item.source",
            "OfficialFlag": "item.official_flag",
        },
        "counts": {
            "topics": len(topics),
            "arithmetic": sum(1 for t in topics if t["domain"] == "Arithmetic"),
            "algebra": sum(1 for t in topics if t["domain"] == "Algebra"),
            "practice_items": sum(
                1 + len(t["we_do"]) + len(t["you_do"]) for t in topics
            ),
        },
        "topics": [
            {
                "topic_id": t["topic_id"],
                "slug": t["slug"],
                "title": t["title"],
                "domain": t["domain"],
                "json": t["slug"] + ".json",
                "html": "html/" + t["slug"] + ".html",
                "prerequisites": t["prerequisites"],
                "counts": {
                    "we_do": len(t["we_do"]),
                    "you_do": len(t["you_do"]),
                    "held_out_samples": len(
                        t["mastery_check"].get("sample_held_out_items", [])
                    ),
                },
            }
            for t in topics
        ],
    }
    with open(os.path.join(HERE, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # HTML
    for t in topics:
        with open(os.path.join(HTML_DIR, t["slug"] + ".html"), "w", encoding="utf-8") as f:
            f.write(render_html(t))
    with open(os.path.join(HTML_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_hub(topics))

    # README (plain text)
    with open(os.path.join(HERE, "README"), "w", encoding="utf-8") as f:
        f.write(render_readme(topics, index))

    # validate JSON round-trips, then validate each file against schema.json
    loaded = {}
    for t in topics:
        with open(os.path.join(HERE, t["slug"] + ".json"), encoding="utf-8") as f:
            loaded[t["slug"]] = json.load(f)
    with open(os.path.join(HERE, "index.json"), encoding="utf-8") as f:
        json.load(f)

    schema_errors = validate_against_schema(loaded)
    if schema_errors:
        print("SCHEMA VALIDATION FAILED:")
        for e in schema_errors:
            print("  - " + e)
        raise SystemExit(1)

    with_questions = sum(
        1 for d in loaded.values()
        if d.get("opening", {}).get("retrieval_starter", {}).get("questions")
    )

    print(f"OK: {len(topics)} topics, "
          f"{index['counts']['practice_items']} practice items, "
          f"{len(topics)+1} html files (incl. hub) + index.json + README.")
    print(f"Schema: all {len(loaded)} lesson JSON files validate against schema.json.")
    print(f"Openings: {with_questions}/{len(loaded)} have opening.retrieval_starter.questions "
          f"(+ prior_knowledge_bridge + learning_intention).")


def render_readme(topics, index):
    lines = []
    A = lines.append
    A("GMATWiz - GMAT Focus Quant (Problem Solving) lesson library")
    A("=" * 60)
    A("")
    A("WHAT THIS IS")
    A("-" * 12)
    A("Authored lesson content for the Quantitative Reasoning section of the")
    A("GMAT Focus Edition (Problem Solving only: arithmetic + algebra; no")
    A("geometry, no Data Sufficiency - per PRD Section 5). Every topic is a")
    A("self-contained lesson built on the same schema and the same evidence-")
    A("based learning model. Content is authored (OfficialFlag=false); scarce")
    A("official questions are reserved as late-stage checkpoints (PRD 13).")
    A("")
    A("PEDAGOGICAL MODEL (PRD Section 2 + Section 9; skills applied)")
    A("-" * 12)
    A("1. Retrieval-practice OPENING (lesson-opening-designer skill):")
    A("   - Do-Now retrieval from memory targeting the exact prerequisites")
    A("     today's topic depends on (Rosenshine Principle 1; Agarwal 2012).")
    A("   - Prior-knowledge BRIDGE that states the connection explicitly")
    A("     (Ausubel advance organiser; Marzano).")
    A("   - LEARNING INTENTION describing learning, not activity (Hattie),")
    A("     plus student-facing success criteria.")
    A("2. Mastery loop I DO -> WE DO -> YOU DO (Archer; PRD 9.2):")
    A("   - I do:  one worked example with think-aloud reasoning.")
    A("   - We do: 2-3 guided items with faded scaffolds + immediate feedback.")
    A("   - You do: 3-5 independent, new exam-style items.")
    A("3. APPLICATION-FIRST (SPOV2, PRD Section 2): in you_do, the explanation")
    A("   is withheld until AFTER an attempt (reveal_explanation_after_attempt).")
    A("   Application creates competence; lessons only create confidence.")
    A("4. ERROR LOG (required, PRD Section 10): every miss carries error-type")
    A("   tags (content gap / reasoning flaw / timing / careless / trap) and")
    A("   becomes spaced re-practice.")
    A("5. MASTERY = >=85% correct on new/held-out items across >=2 spaced")
    A("   sessions with delay (PRD Section 9.2) - not flashcard recall alone.")
    A("")
    A("SCHEMA (see schema.json - JSON Schema draft-07)")
    A("-" * 12)
    A("Each <slug>.json has: schema_version, topic_id, slug, title, section,")
    A("question_type, domain, exam, estimated_minutes, prerequisites,")
    A("learning_objectives, pedagogical_model, opening{do_now, retrieval_starter,")
    A("prior_knowledge_bridge, learning_intention, success_criteria,")
    A("opening_script}, i_do, we_do[], you_do[], mastery_check, citations[], tags[].")
    A("")
    A("Every practice item (i_do, we_do[], you_do[], held-out samples) maps 1:1")
    A("onto the PRD Section 8 'GMAT PS' notetype so the app can import directly:")
    A("  Stem=stem  OptionA..E=options.A..E  Correct=correct  Explanation=explanation")
    A("  Topic=topic  Difficulty=difficulty  Source=source  OfficialFlag=official_flag")
    A("")
    A("COVERAGE (" + str(index["counts"]["topics"]) + " leaf topics, "
      + str(index["counts"]["practice_items"]) + " practice items)")
    A("-" * 12)
    for dom in ["Arithmetic", "Algebra"]:
        A(dom + ":")
        for t in topics:
            if t["domain"] == dom:
                A("  - {:<26} {}".format(t["title"], t["topic_id"]))
                A("      json: {:<26} html: html/{}.html".format(
                    t["slug"] + ".json", t["slug"]))
        A("")
    A("FILES")
    A("-" * 12)
    A("  schema.json     JSON Schema (draft-07) for a topic file")
    A("  index.json      manifest: topics, paths, counts, notetype mapping")
    A("  <slug>.json     one lesson per topic (18 files)")
    A("  html/<slug>.html  self-contained Tufte-clean review page per topic")
    A("  html/index.html   hub linking every topic page")
    A("  build.py        authoring source of truth; regenerates all of the above")
    A("  README          this file")
    A("")
    A("REGENERATE")
    A("-" * 12)
    A("  cd gmatwiz/lessons && python3 build.py")
    A("  (writes only inside gmatwiz/lessons/; touches no repo source.)")
    A("")
    A("CITATIONS")
    A("-" * 12)
    A("Each lesson links a high-trust primary source (OpenStax open textbooks,")
    A("Khan Academy, and mba.com for exam structure). See each topic's HTML")
    A("'Primary source' box and the citations[] array in its JSON.")
    A("")
    return "\n".join(lines)


if __name__ == "__main__":
    build()
