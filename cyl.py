#!/usr/bin/env python3

import argparse
import base64
import http.client
import datetime
import json
import os
import pathlib
import random
import re
import shutil
import ssl
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.parse
import urllib.request
VERSION = "1.1.0"
API = "https://api.c4mpus.com"
API_HOST = "api.c4mpus.com"
ORIGIN = "https://c4mpus.com"
# Cloudflare returns 1010 ("browser signature") for the default Python-urllib UA.
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:157.0) "
              "Gecko/20100101 Firefox/157.0")
YEARS = ["Year One", "Year Two", "Year Three", "Year Four"]
TOKEN_FILE = pathlib.Path.home() / ".c4mpus_token"
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+")

# ---------------------------------------------------------------- presentation

# Warm ink-and-gold palette: one hue carries the brand, muted accents carry
# meaning. (hex, fallback ANSI code for terminals without truecolor.)
PALETTE = {
    "gold":   ("d9a441", "33"),      # brand / in-progress
    "ember":  ("8a5f22", "33;2"),    # the logo's drop shadow
    "cream":  ("ded5c6", "37"),      # primary text
    "sage":   ("3fb950", "32"),      # done / success
    "azure":  ("58a6ff", "94"),      # progress bar fill
    "teal":   ("5f9ea0", "36"),      # interactive, numbers
    "brick":  ("bf5b48", "31"),      # failure
    "stone":  ("7d766c", "90"),      # secondary text
    "slate":  ("4a453d", "90"),      # rules, empty bar track
}

# Logo themes: (face, shadow). Each is a single hue at two luminances, so the
# font's built-in drop shadow reads as a shadow instead of a second colour.
THEMES = {
    "gold":      (("d9a441", "33"), ("8a5f22", "33;2")),   # default: warm amber
    "mono":      (("ded5c6", "37"), ("4a453d", "90")),     # ink on paper
    "blueprint": (("7aa2c4", "36"), ("2f4858", "34;2")),   # drafting blue
    "plum":      (("b07aa8", "35"), ("553049", "35;2")),   # muted violet
}
THEME = "gold"

# (filled, empty) glyph pairs for the progress bar.
BAR_STYLES = {
    "boxes":  ("■", "□"),
    "blocks": ("▰", "▱"),
    "solid":  ("█", "░"),
}
BAR = "boxes"

FAREWELLS = ("Bye.", "Adios.", "Au revoir.")

COLOR = True
TRUECOLOR = True
PROGRESS = True

# Pixel-art mortarboard, two bitmap rows per terminal row via half blocks
# (the trick kiterunner's banner uses). Each cell is an ink key from ART_INK,
# "." is transparent, so the art inherits the terminal background.
ART = [
    "..........GGGG..........",
    ".......GGGGGGGGGG.......",
    "....GGGGGGGGGGGGGGGG....",
    ".GGGGGGGGGGGGGGGGGGGGGG.",
    "...EEEEEEEEEEEEEEEEEE.C.",
    "......EEEEEEEEEEEE....C.",
    ".......CCCCCCCCCC.....C.",
    ".......EEEEEEEEEE.....C.",
    "........EEEEEEEE.....KKK",
    ".........EEEEEE......KKK",
    "......................KK",
    "........................",
]
# G/E follow the logo theme, so --theme recolours the cap with the wordmark.
ART_INK = {"G": "face", "E": "shadow", "C": "cream", "K": "brick"}

LOGO = [
    " ██████╗██╗   ██╗██╗     ",
    "██╔════╝╚██╗ ██╔╝██║     ",
    "██║      ╚████╔╝ ██║     ",
    "██║       ╚██╔╝  ██║     ",
    "╚██████╗   ██║   ███████╗",
    " ╚═════╝   ╚═╝   ╚══════╝",
]
SHADOW_GLYPHS = set("╗╝╚╔║═")


def tint(pair, text, bold=False):
    if not COLOR:
        return text
    hexcode, fallback = pair
    if TRUECOLOR:
        r, g, b = (int(hexcode[i:i + 2], 16) for i in (0, 2, 4))
        code = f"38;2;{r};{g};{b}"
    else:
        code = fallback
    return f"\033[{'1;' if bold else ''}{code}m{text}\033[0m"


def col(name, text, bold=False):
    return tint(PALETTE[name], text, bold=bold)


def b(text):  return col("cream", text, bold=True)
def mute(t):  return col("stone", t)


def rgb(hex6, bg=False):
    r, g, b = (int(hex6[i:i + 2], 16) for i in (0, 2, 4))
    return f"\033[{48 if bg else 38};2;{r};{g};{b}m"


def art_lines():
    """The bitmap as half-block rows: upper pixel is the glyph's foreground,
    lower pixel its background. Needs truecolor, so returns [] without it."""
    if not (COLOR and TRUECOLOR):
        return []
    face, shadow = THEMES.get(THEME, THEMES["gold"])
    ink = {"face": face[0], "shadow": shadow[0],
           "cream": PALETTE["cream"][0], "brick": PALETTE["brick"][0]}

    def hue(ch):
        return ink.get(ART_INK.get(ch, ""), "")

    lines = []
    for top, bottom in zip(ART[::2], ART[1::2]):
        cells = []
        for t, b in zip(top, bottom):
            up, down = hue(t), hue(b)
            if up and down:
                cells.append(rgb(up) + rgb(down, True) + "▀\033[0m")
            elif up:
                cells.append(rgb(up) + "▀\033[0m")
            elif down:
                cells.append(rgb(down) + "▄\033[0m")
            else:
                cells.append(" ")
        lines.append("".join(cells))
    return lines


def logo_lines():
    """Two-tone wordmark: solid faces in the theme hue, the font's own shadow
    in a darker value of the same hue."""
    face, shadow = THEMES.get(THEME, THEMES["gold"])
    out = []
    for line in LOGO:
        glyphs = []
        for ch in line:
            if ch == "█":
                glyphs.append(tint(face, ch, bold=True))
            elif ch in SHADOW_GLYPHS:
                glyphs.append(tint(shadow, ch))
            else:
                glyphs.append(ch)
        out.append("".join(glyphs))
    return out


def banner():
    """The cap beside the wordmark, or the wordmark alone on a terminal
    without truecolor (half blocks need per-cell backgrounds)."""
    art, logo = art_lines(), logo_lines()
    room = shutil.get_terminal_size((88, 24)).columns
    if art and room >= len(ART[0]) + 25 + 4:
        for left, right in zip(art, logo):
            print("  " + left + "  " + right)
    else:
        for line in logo:
            print("  " + line)
    print("  " + col("cream", "complete your lessons") + "  "
          + col("slate", "·") + "  " + mute(f"v{VERSION}"))
    print("  " + col("slate", "─" * 25))


def bar(done, total, width=22):
    full, empty = BAR_STYLES.get(BAR, BAR_STYLES["boxes"])
    if not total:
        return col("slate", empty * width)
    filled = round(width * done / total)
    return col("azure", full * filled) + col("slate", empty * (width - filled))


def pct(done, total):
    return f"{round(100 * done / total) if total else 0:>3}%"


def human_time(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60:02d}s"
    return f"{seconds // 3600}h {(seconds % 3600) // 60:02d}m"


def rule(label=""):
    width = min(shutil.get_terminal_size((88, 24)).columns, 88)
    if label:
        print("\n" + col("gold", label.upper(), bold=True) + " "
              + col("slate", "─" * max(width - len(label) - 1, 0)))
    else:
        print(col("slate", "─" * width))


# ------------------------------------------------------------------------ auth

GRAB_TOKEN_HELP = f"""\
{b('Get your token from the browser:')}
  1. Open https://c4mpus.com and log in
  2. Press F12 -> {col('teal', 'Network')} tab, click any request to api.c4mpus.com
  3. Right-click it -> {col('teal', 'Copy')} -> {col('teal', 'Copy as cURL')}

Then paste it here. {mute('cyl finds the token inside whatever you paste -')}
{mute('a raw eyJ... string, a Bearer header, or a whole cURL command.')}"""


class ApiError(Exception):
    pass


def extract_jwt(text):
    """Pull a JWT out of anything: raw token, Bearer header, cURL command."""
    match = JWT_RE.search(text or "")
    return match.group(0) if match else None


def read_clipboard():
    for cmd in (["pbpaste"], ["wl-paste"], ["xclip", "-o", "-selection", "clipboard"],
                ["xsel", "-b"], ["powershell.exe", "-command", "Get-Clipboard"]):
        if shutil.which(cmd[0]):
            try:
                return subprocess.run(cmd, capture_output=True, text=True,
                                      timeout=5).stdout
            except Exception:
                return None
    return None


def decode_token(token):
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return None


def describe_token(token):
    claims = decode_token(token) or {}
    name = " ".join(x for x in (claims.get("firstname"), claims.get("lastname")) if x)
    who = f"{name} ({claims['username']})" if name and claims.get("username") else (
        claims.get("username") or claims.get("email") or "unknown user")
    exp = datetime.datetime.fromtimestamp(claims["exp"]) if claims.get("exp") else None
    return who, exp, claims


def save_token(token):
    TOKEN_FILE.write_text(token + "\n")
    TOKEN_FILE.chmod(0o600)


def prompt_for_token():
    print("\n" + GRAB_TOKEN_HELP + "\n")
    for attempt in range(3):
        raw = input(col("teal", "Paste here") + mute(" (or press Enter to read your clipboard)")
                    + col("teal", " > "))
        if not raw.strip():
            raw = read_clipboard() or ""
            if raw.strip():
                print(mute("  read from clipboard"))
        token = extract_jwt(raw)
        if token and decode_token(token):
            save_token(token)
            who, _, _ = describe_token(token)
            print(col("sage", f"  ✓ saved {who} to {TOKEN_FILE}") + mute(" (mode 600)"))
            return token
        print(col("brick", "  Couldn't find a token in that.")
              + mute(f" {2 - attempt} attempt(s) left."))
    sys.exit("Giving up - no usable token.")


def load_token(cli_token, interactive):
    for val in (cli_token,
                os.environ.get("CYL_TOKEN"),
                os.environ.get("C4MPUS_TOKEN"),
                TOKEN_FILE.read_text() if TOKEN_FILE.exists() else None):
        if val and extract_jwt(val):
            return extract_jwt(val)
    if interactive and sys.stdin.isatty():
        return prompt_for_token()
    sys.exit("No token. Run cyl with no arguments to set one up, "
             "or pass --token / set CYL_TOKEN.")


# ---------------------------------------------------------------------- client

class Client:
    """Keeps one TLS connection open per thread - a fresh handshake per request
    was costing more than the requests themselves."""

    def __init__(self, token, timeout=30):
        self.token = token
        self.timeout = timeout
        self.ssl = self._ssl()
        self._local = threading.local()

    @staticmethod
    def _ssl():
        """python.org builds on macOS ship without a usable trust store."""
        ctx = ssl.create_default_context()
        if ctx.cert_store_stats()["x509_ca"] == 0:
            try:
                import certifi
                ctx.load_verify_locations(certifi.where())
            except ImportError:
                sys.exit("No CA certificates available. Run "
                         "'/Applications/Python 3.11/Install Certificates.command' "
                         "or 'pip install certifi'.")
        return ctx

    def _conn(self):
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = http.client.HTTPSConnection(API_HOST, context=self.ssl,
                                               timeout=self.timeout)
            self._local.conn = conn
        return conn

    def _drop(self):
        conn = getattr(self._local, "conn", None)
        self._local.conn = None
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    def close(self):
        self._drop()

    def _headers(self, has_body):
        h = {"User-Agent": USER_AGENT,
             "Authorization": "Bearer " + self.token,
             "Accept": "application/json, text/plain, */*",
             "Accept-Language": "en-US,en;q=0.9",
             "Accept-Encoding": "identity",
             "Origin": ORIGIN,
             "Referer": ORIGIN + "/",
             "Sec-Fetch-Dest": "empty",
             "Sec-Fetch-Mode": "cors",
             "Sec-Fetch-Site": "same-site",
             "Connection": "keep-alive"}
        if has_body:
            h["Content-Type"] = "application/json"
        return h

    def _call(self, method, path, body=None, _retry=True):
        data = json.dumps(body).encode() if body is not None else None
        try:
            conn = self._conn()
            conn.request(method, path, body=data, headers=self._headers(data is not None))
            resp = conn.getresponse()
            payload = resp.read()
            status, reason = resp.status, resp.reason
            if resp.will_close:
                self._drop()
        except (http.client.HTTPException, OSError) as e:
            # A pooled connection the server already closed fails on reuse; retry once.
            self._drop()
            if _retry:
                return self._call(method, path, body, _retry=False)
            raise ApiError(f"network error on {method} {path}: {e}")

        if status >= 400:
            detail = payload[:300].decode("utf-8", "replace")
            if status in (401, 403) and "1010" not in detail:
                raise ApiError(f"{status} {reason} - token rejected or expired.")
            raise ApiError(f"{status} {reason} on {method} {path}: {detail}")
        return json.loads(payload or b"{}")

    def modules(self, years=YEARS):
        out, seen = [], set()
        for year in years:
            q = urllib.parse.urlencode({"year": year}, quote_via=urllib.parse.quote)
            for m in self._call("GET", f"/users/my-learnings?{q}").get("modules") or []:
                slug = m.get("moduleSlug")
                if slug and slug not in seen:
                    seen.add(slug)
                    out.append({"slug": slug,
                                "title": (m.get("moduleTitle") or slug).strip(),
                                "code": (m.get("moduleCode") or "").strip(),
                                "year": m.get("year") or year})
        return out

    def lessons(self, slug):
        res = self._call("GET", f"/lessons/{urllib.parse.quote(slug, safe='')}/weekly/public")
        return [{"id": l["_id"], "title": (l.get("lessonTitle") or l["_id"]).strip(),
                 "week": g.get("week"), "assessments": len(l.get("assessments") or [])}
                for g in res.get("lessons") or [] for l in g.get("lessons") or []]

    def completed_ids(self):
        res = self._call("GET", "/users/completed-lessons")
        return {c["lesson"] for c in res.get("completedLessons") or [] if c.get("lesson")}

    def status(self, slug, lesson_id):
        return self._call("POST", "/tracking/lesson-status",
                          {"lesson": lesson_id, "moduleSlug": slug}).get("lessonStatus")

    def start(self, slug, lesson_id):
        return self._call("POST", "/tracking/start",
                          {"moduleSlug": slug, "lesson": lesson_id,
                           "startDate": int(time.time() * 1000)})

    def mark_complete(self, slug, lesson_id):
        return self._call("POST", "/tracking/mark-as-complete",
                          {"moduleSlug": slug, "lesson": lesson_id, "isCompleted": True,
                           "endDate": int(time.time() * 1000)})


# ------------------------------------------------------------------- gathering

def scan(client, modules, done=None, note="scanning", workers=8):
    """Attach lesson data to each module, fetched in parallel. Read-only."""
    done = client.completed_ids() if done is None else done
    show = PROGRESS and len(modules) > 1
    counter = {"n": 0}
    lock = threading.Lock()

    def fetch(m):
        lessons = client.lessons(m["slug"])
        if show:
            with lock:
                counter["n"] += 1
                print("\r  " + mute(f"{note} {counter['n']}/{len(modules)}"),
                      end="", flush=True)
        todo = [l for l in lessons if l["id"] not in done]
        return {**m, "lessons": lessons, "todo": todo,
                "total": len(lessons), "done": len(lessons) - len(todo)}

    if len(modules) == 1:
        rows = [fetch(modules[0])]
    else:
        with ThreadPoolExecutor(max_workers=min(workers, len(modules))) as pool:
            rows = list(pool.map(fetch, modules))
    if show:
        print("\r" + " " * 72 + "\r", end="")
    return rows


# --------------------------------------------------------------------- status

def render_status(rows, scope):
    total = sum(r["total"] for r in rows)
    done = sum(r["done"] for r in rows)
    finished = [r for r in rows if r["total"] and r["done"] == r["total"]]
    untouched = [r for r in rows if r["total"] and not r["done"]]
    partial = [r for r in rows if r["done"] and r["done"] < r["total"]]
    weeks = {(r["slug"], l["week"]) for r in rows for l in r["lessons"]}
    assessments = sum(l["assessments"] for r in rows for l in r["lessons"])

    rule(scope)
    print(f"  {bar(done, total, 34)}  {b(pct(done, total))}   "
          f"{col('teal', str(done))}{mute('/' + str(total))} lessons")
    print(f"  {mute('modules')} {len(rows)}   {mute('weeks')} {len(weeks)}   "
          f"{mute('assessments')} {assessments}   "
          f"{mute('remaining')} {col('gold', str(total - done))}")

    years = []
    for r in rows:
        if r["year"] not in years:
            years.append(r["year"])
    if len(years) > 1:
        rule("by year")
        for y in years:
            yr = [r for r in rows if r["year"] == y]
            yd, yt = sum(r["done"] for r in yr), sum(r["total"] for r in yr)
            nfin = sum(1 for r in yr if r["total"] and r["done"] == r["total"])
            print(f"  {y:<11} {bar(yd, yt)} {b(pct(yd, yt))}  "
                  + col("teal", f"{yd:>4}") + mute(f"/{yt}".ljust(8))
                  + mute(f"{len(yr)} modules, {nfin} finished"))
            print()

    rule("highlights")
    if partial:
        closest = min(partial, key=lambda r: r["total"] - r["done"])
        left = closest["total"] - closest["done"]
        print("  " + mute(f"{'closest to done':<22}") + f" {closest['title']} "
              + mute("· ") + col("gold", f"{left} left"))
    if rows:
        biggest = max(rows, key=lambda r: r["total"] - r["done"])
        if biggest["total"] - biggest["done"]:
            print("  " + mute(f"{'biggest gap':<22}") + f" {biggest['title']} "
                  + mute("· ") + col("brick", f"{biggest['total'] - biggest['done']} left"))
    print("  " + mute(f"{'finished modules':<22}") + " "
          + col("sage", str(len(finished))) + mute(f" of {len(rows)}"))
    if untouched:
        print("  " + mute(f"{'not started':<22}") + " "
              + col("stone", f"{len(untouched)} modules"))

    worst_weeks = {}
    for r in rows:
        for l in r["todo"]:
            worst_weeks[l["week"]] = worst_weeks.get(l["week"], 0) + 1
    if worst_weeks:
        top = sorted(worst_weeks.items(), key=lambda kv: -kv[1])[:5]
        print("  " + mute(f"{'weeks most behind':<22}") + " "
              + mute(" · ").join(f"wk{w} {col('gold', str(n))}" for w, n in top))
    print()


def status_flow(client, args, modules=None):
    modules = modules or client.modules()
    print(mute("\n  Reading your progress across all modules..."))
    rows = scan(client, modules, note="reading")
    render_status(rows, "overall progress")
    return rows


# ------------------------------------------------------------------ completion

def run_completion(client, jobs, delay, dwell):
    ok = failed = 0
    started = time.monotonic()
    current = None
    for i, (module, lesson) in enumerate(jobs, 1):
        if module["slug"] != current:
            current = module["slug"]
            print(f"\n  {b(module['title'])}")
        eta = ""
        if i > 1:
            per = (time.monotonic() - started) / (i - 1)
            eta = mute("  eta " + human_time(per * (len(jobs) - i + 1)))
        label = f"    {mute(f'[{i}/{len(jobs)}]')} {lesson['title'][:46]:<46}"
        try:
            if client.status(module["slug"], lesson["id"]) is None:
                client.start(module["slug"], lesson["id"])
                time.sleep(dwell)
            res = client.mark_complete(module["slug"], lesson["id"])
            if res.get("success"):
                ok += 1
                print(f"{label} {col('sage', 'done')}{eta}")
            else:
                failed += 1
                print(f"{label} {col('gold', 'unexpected')} {json.dumps(res)[:110]}")
        except ApiError as e:
            failed += 1
            print(f"{label} {col('brick', 'FAILED')} {e}")
            if "token rejected" in str(e):
                print("\n  " + col("gold", "Token died mid-run.")
                      + " Refresh it and re-run - finished lessons are skipped.")
                break
        if i < len(jobs):
            time.sleep(delay)
    return ok, failed


def confirm(question, default_no=True):
    suffix = "[y/N]" if default_no else "[Y/n]"
    answer = input(f"\n{question} {mute(suffix)} ").strip().lower()
    return answer in ("y", "yes") if default_no else answer not in ("n", "no")


def execute(client, rows, args, what):
    jobs = [(r, l) for r in rows for l in r["todo"]]
    if not jobs:
        print("\n  " + col("sage", f"Nothing to do - {what} is already complete."))
        return

    rule(f"plan · {what}")
    if len(rows) > 1:
        for r in rows:
            left = len(r["todo"])
            print(f"    {r['title'][:52]:<52} "
                  + (f"{left:>4} remaining" if left else mute("   - complete")))
    else:
        for _, l in jobs:
            print("    " + mute(f"wk{l['week']:<5}") + f" {l['title']}")
    print(f"\n  {col('teal', str(len(jobs)))} lesson(s) across "
          f"{col('teal', str(len({r['slug'] for r, _ in jobs})))} module(s)")

    est = len(jobs) * (args.delay + args.dwell + 0.35)
    if not (args.yes or confirm(f"  Complete all {len(jobs)} lesson(s)? "
                                + mute("~" + human_time(est)))):
        print(mute("  Cancelled - nothing was sent."))
        return

    ok, failed = run_completion(client, jobs, args.delay, args.dwell)
    print(f"\n  {col('sage', str(ok) + ' completed')}"
          + (f", {col('brick', str(failed) + ' failed')}" if failed else "") + ".")


def choose(title, rows, labeller, extras=()):
    """Numbered menu with lettered extras. Returns (kind, value)."""
    print(f"\n  {b(title)}")
    for i, row in enumerate(rows, 1):
        print(f"    {col('teal', f'{i:>2}')}{mute(')')} {labeller(row)}")
    for key, label in extras:
        print(f"     {col('gold', key)}{mute(')')} {label}")
    print(f"     {mute('q)')} {mute('quit')}")
    valid = {k for k, _ in extras}
    while True:
        answer = input("\n  " + col("teal", "> ")).strip().lower()
        if answer in ("q", "quit", "exit"):
            return "quit", None
        if answer in valid:
            return "extra", answer
        if answer.isdigit() and 1 <= int(answer) <= len(rows):
            return "row", rows[int(answer) - 1]
        print(mute(f"    Enter 1-{len(rows)}"
                   + (", " + "/".join(sorted(valid)) if valid else "") + ", or q."))


def progress_tag(done, total):
    """The state chip shared by the year and module choosers."""
    if not total:
        return mute("(no lessons)")
    if done >= total:
        return col("sage", "(completed)")
    if not done:
        return mute("(not started)")
    return col("gold", f"{total - done} left")


def module_label(r):
    """One line for a scanned module in a chooser: title, count, state."""
    return (f"{r['title'][:44]:<44} "
            + mute(f"{r['done']}/{r['total']}".rjust(7)) + "  "
            + progress_tag(r["done"], r["total"]))


def complete_flow(client, args, modules):
    years = []
    for m in modules:
        if m["year"] not in years:
            years.append(m["year"])

    while True:
        # Re-read every loop so a year finished in the last run reads as done.
        print(mute(f"\n  Reading {len(modules)} module(s)..."))
        all_rows = scan(client, modules, note="reading")

        def year_label(y):
            yr = [r for r in all_rows if r["year"] == y]
            yd, yt = sum(r["done"] for r in yr), sum(r["total"] for r in yr)
            return (f"{y:<12}" + mute(f"{len(yr)} modules".ljust(11)) + "  "
                    + mute(f"{yd}/{yt}".rjust(8)) + "  " + progress_tag(yd, yt))

        total_done = sum(r["done"] for r in all_rows)
        total_all = sum(r["total"] for r in all_rows)
        kind, year = choose("Which year?", years, year_label,
                            extras=[("a", col("gold", "All years", bold=True)
                                     + f" · every module ({len(modules)})  "
                                     + progress_tag(total_done, total_all))])
        if kind == "quit":
            return
        if kind == "extra":
            execute(client, all_rows, args, "All years")
            if not confirm("  Back to the menu?"):
                return
            continue

        rows = [r for r in all_rows if r["year"] == year]

        kind, module = choose(
            f"{year} · which module?", rows, module_label,
            extras=[("a", col("gold", "All modules", bold=True)
                     + f" in {col('cream', year)} ({len(rows)})"),
                    ("b", col("cream", "Back") + mute(" to years"))])
        if kind == "quit":
            return
        if kind == "extra" and module == "b":
            continue

        targets = rows if kind == "extra" else [module]
        what = f"all of {year}" if kind == "extra" else module["title"]
        execute(client, targets, args, what)
        if not confirm("  Back to the menu?"):
            return


def main_menu(client, args):
    print(mute("\n  Loading your modules..."))
    modules = client.modules()
    if not modules:
        sys.exit("No enrolled modules came back.")

    while True:
        kind, choice = choose(
            "What do you want to do?",
            [("status", "Check progress", "totals, a bar per year, and highlights"),
             ("complete", "Complete lessons", "pick a year and module, or do them all")],
            lambda row: col("cream", f"{row[1]:<18}") + "  " + mute(row[2]))
        if kind == "quit":
            print(mute(f"\n  {random.choice(FAREWELLS)}\n"))
            return
        if choice[0] == "status":
            rows = status_flow(client, args, modules)
            if confirm("  Complete lessons now?"):
                complete_flow(client, args, modules)
        else:
            complete_flow(client, args, modules)


# ---------------------------------------------------------------- subcommands

def resolve_modules(client, args):
    everything = client.modules()
    if args.all:
        return everything
    wanted, problems = [], []
    for want in args.module:
        exact = next((m for m in everything if m["slug"] == want), None)
        if exact:
            wanted.append(exact)
            continue
        near = [m for m in everything
                if want.lower() in m["slug"].lower() or want.lower() in m["title"].lower()]
        if len(near) == 1:
            wanted.append(near[0])
        elif near:
            problems.append(f"{want!r} is ambiguous: " + ", ".join(m["slug"] for m in near))
        else:
            problems.append(f"{want!r} matched no enrolled module")
    if problems:
        sys.exit("\n".join(problems) + "\n\nRun `cyl modules` to see the list.")
    return wanted


def cmd_modules(client, args):
    for m in client.modules():
        print(f"{m['year']:<12} {m['slug']:<58} {m['title']}")


def cmd_status(client, args):
    modules = resolve_modules(client, args) if (args.module or args.all) else client.modules()
    rows = scan(client, modules, note="reading")
    render_status(rows, "overall progress")


def cmd_lessons(client, args):
    for r in scan(client, resolve_modules(client, args)):
        print(f"\n{b(r['title'])} {mute('[' + r['slug'] + ']')}  "
              f"{r['done']}/{r['total']} complete")
        todo = {l["id"] for l in r["todo"]}
        for l in r["lessons"]:
            mark = " " if l["id"] in todo else col("sage", "x")
            print(f"  {mark}  " + mute(f"wk{l['week']:<5}") + "  "
                  + mute(l["id"]) + f"  {l['title']}")


def cmd_complete(client, args):
    modules = resolve_modules(client, args)
    done = set() if args.redo else client.completed_ids()
    rows = scan(client, modules, done)
    if args.dry_run:
        jobs = [(r, l) for r in rows for l in r["todo"]]
        for r, l in jobs:
            print(f"  {r['slug']:<58} wk{str(l['week']):<4} {l['title']}")
        print(f"\n{len(jobs)} lesson(s). " + col("gold", "Dry run - nothing was sent."))
        return
    execute(client, rows, args, "selection")


def main():
    global COLOR, TRUECOLOR, PROGRESS, THEME, BAR
    p = argparse.ArgumentParser(
        prog="cyl",
        description="cyl - Complete Your Lessons. Progress dashboard and bulk lesson "
                    "completion for c4mpus.com. Run with no arguments for the menu.")
    p.add_argument("--token", help="bearer token (else CYL_TOKEN or ~/.c4mpus_token)")
    p.add_argument("--delay", type=float, default=0.4,
                   help="seconds between lessons (default 0.4)")
    p.add_argument("--dwell", type=float, default=0.25,
                   help="seconds between start and mark-as-complete (default 0.25)")
    p.add_argument("-y", "--yes", action="store_true", help="skip confirmation prompts")
    p.add_argument("--no-color", action="store_true", help="disable coloured output")
    p.add_argument("-q", "--quiet", action="store_true", help="hide the startup banner")
    p.add_argument("--theme", choices=sorted(THEMES), default="gold",
                   help="logo colour theme (default gold)")
    p.add_argument("--bar", choices=sorted(BAR_STYLES), default="boxes",
                   help="progress bar glyphs (default boxes)")
    p.add_argument("--version", action="version", version=f"cyl {VERSION}")
    sub = p.add_subparsers(dest="cmd")

    def add_targets(sp):
        sp.add_argument("-m", "--module", action="append", default=[],
                        help="module slug (or unique substring); repeatable")
        sp.add_argument("--all", action="store_true", help="every enrolled module, every year")

    sub.add_parser("modules", help="list enrolled modules").set_defaults(fn=cmd_modules)

    sp = sub.add_parser("status", help="progress dashboard")
    add_targets(sp)
    sp.set_defaults(fn=cmd_status)

    sp = sub.add_parser("lessons", help="list lessons and completion state")
    add_targets(sp)
    sp.set_defaults(fn=cmd_lessons)

    sp = sub.add_parser("complete", help="mark lessons complete non-interactively")
    add_targets(sp)
    sp.add_argument("-n", "--dry-run", action="store_true", help="show the plan, send nothing")
    sp.add_argument("--redo", action="store_true", help="include already-completed lessons")
    sp.set_defaults(fn=cmd_complete)

    args = p.parse_args()
    PROGRESS = sys.stdout.isatty()
    COLOR = (sys.stdout.isatty() and not args.no_color
             and not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb")
    TRUECOLOR = os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit")
    THEME = args.theme
    BAR = args.bar

    if args.cmd in ("lessons", "complete") and not args.module and not args.all:
        sys.exit("Pass -m <module> (repeatable) or --all, "
                 "or run with no arguments to pick interactively.")

    if args.cmd is None and not args.quiet:
        banner()

    token = load_token(args.token, interactive=args.cmd is None)
    who, exp, _ = describe_token(token)
    if exp:
        left = exp - datetime.datetime.now()
        if left.total_seconds() < 0:
            TOKEN_FILE.unlink(missing_ok=True)
            sys.exit(col("brick", f"Token expired {exp:%Y-%m-%d %H:%M}") + " - discarded.\n\n"
                     + GRAB_TOKEN_HELP)
        tone = "gold" if left.days < 1 else "stone"
        print(f"  {col('sage', '✓')} {b(who)}  "
              + col(tone, f"token valid {left.days}d {left.seconds // 3600}h")
              + mute(f" · until {exp:%d %b %H:%M}"))

    try:
        if args.cmd is None:
            main_menu(Client(token), args)
        else:
            args.fn(Client(token), args)
    except ApiError as e:
        sys.exit(col("brick", "API error: ") + str(e))
    except (KeyboardInterrupt, EOFError):
        sys.exit(mute("\n  Interrupted."))


if __name__ == "__main__":
    main()
