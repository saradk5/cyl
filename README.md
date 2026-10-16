# cyl — Complete Your Lessons

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/cyl-dark.png">
  <img src="assets/cyl-dark.svg" width="632" alt="cyl — complete your lessons">
</picture>

[![Python](https://img.shields.io/badge/python-3.8+-d9a441.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-brightgreen.svg)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen.svg)](#requirements)
[![Single file](https://img.shields.io/badge/single%20file-cyl.py-blue.svg)](cyl.py)
[![Version](https://img.shields.io/badge/version-1.1.0-8a5f22.svg)](cyl.py)

#### *c4mpus shows you a percentage. cyl shows you what to actually do about it.*

cyl is a single-file terminal client for [c4mpus.com](https://c4mpus.com). It reads
your whole enrolment at once and reports more — and more accurate — statistics about
your module progress than c4mpus itself does, then marks lessons complete in bulk
through the same API the website uses.

## Why This Exists

c4mpus can tell you a module is at 83%. It cannot tell you *which* lessons are
missing, how that compares to your other fourteen modules, or which three modules are
one lesson away from done. To find out, you click into every module, one at a time,
and count by hand. There is no view that spans years.

cyl reads your entire enrolment in parallel and puts it in one screen: totals, a bar
per year, the modules within a lesson or two of finished, the one furthest behind, how
many assessments are still waiting, and how long clearing the rest would take. The
numbers are also stricter than the platform's — a full bar and `100%` mean every
lesson is genuinely done, so `686/689` reads `99%` rather than rounding up, and any
progress at all reads at least `1%` rather than showing as nothing.

Marking lessons complete is the other half. On the website it is one click per lesson
through a page that reloads between each one, so a module carrying seventy outstanding
lessons is seventy separate round trips. cyl does that part for you — in order,
throttled, and only after you have seen the exact plan and confirmed it.

> **cyl is not a shortcut around studying.** It does not watch your lectures, read
> your notes, or sit your assessments, and nothing it does will teach you the
> material. Read the course content, do the work, earn the understanding — then let
> cyl take the part that was never learning in the first place: clicking *mark as
> complete* several hundred times.

> **Completions are real and there is no undo.** The moment you confirm, cyl marks
> those lessons on your actual c4mpus account. cyl has no un-complete command and the
> API offers no obvious way back. `status` only ever reads, and `--dry-run` prints the
> plan while sending nothing — use both freely.

## Setup

You need a c4mpus account, a terminal, and Python 3.8 or newer. Nothing else —
cyl uses only the standard library.

**1. Check Python is there**
```bash
python3 --version
```
Anything from `3.8` up is fine. On Windows `python3` often doesn't exist — use `py`
instead, everywhere in this guide. If you get `command not found`, install from
[python.org](https://www.python.org/downloads/) and on Windows tick
**"Add Python to PATH"** — it's easy to miss and nothing works without it.

**2. Clone the repository**
```bash
git clone https://github.com/saradk5/cyl.git
cd cyl
```
No `git`? cyl is one file — grab it on its own:
```bash
curl -O https://raw.githubusercontent.com/saradk5/cyl/main/cyl.py
```
Or download [`cyl.py`](https://github.com/saradk5/cyl/blob/main/cyl.py) from the
repository page and `cd` to wherever you saved it. Run `ls` (or `dir` on Windows) and
you should see `cyl.py`.

**3. Log in**
```bash
python3 cyl.py login
```
cyl prints the steps and takes the token off your clipboard. See
[Your token](#your-token) for where it lands and how to revoke it.

**4. Look around — this changes nothing**
```bash
python3 cyl.py status
```

**5. Run it properly**
```bash
python3 cyl.py
```
With no arguments you get the guided menu, which is the best way in.

## Commands

| Command | What it does |
| --- | --- |
| *(none)* | the interactive menu — the recommended way in |
| `login` | get and save a token; `--snippet` prints just the JavaScript |
| `logout` | delete the saved token from this machine |
| `modules` | one line per enrolled module: year, slug, title |
| `status` | the progress dashboard |
| `lessons` | every lesson with its completion mark |
| `complete` | mark lessons complete without the menu |

```bash
python3 cyl.py status --all                       # everything
python3 cyl.py lessons -m digital-forensic        # a unique substring is enough
python3 cyl.py complete -m crypto -m forensic     # -m repeats
python3 cyl.py complete --all --dry-run           # print the plan, send nothing
python3 cyl.py complete -m crypto --redo          # re-send completed lessons too
```

Any substring matching exactly one module works. Match several and cyl lists the
candidates and stops rather than guessing. `status` with no target covers everything;
`lessons` and `complete` deliberately require `-m` or `--all`, so a bare `complete`
can never touch your whole degree by accident.

## Options

| Flag | Default | Purpose |
| --- | --- | --- |
| `--token '<jwt>'` | — | use this token instead of the saved one |
| `--delay` | `0.4` | seconds between lessons |
| `--dwell` | `0.25` | seconds between *start* and *mark complete* |
| `-y`, `--yes` | off | skip confirmations — **use with care** |
| `-n`, `--dry-run` | off | `complete` only: show the plan, send nothing |
| `--redo` | off | `complete` only: include already-completed lessons |
| `-q`, `--quiet` | off | hide the banner |
| `--no-color` | off | plain text; `NO_COLOR` and `TERM=dumb` also respected |
| `--theme` | `gold` | `gold`, `mono`, `blueprint`, `plum` |
| `--bar` | `boxes` | `boxes` ■□, `blocks` ▰▱, `solid` █░ |
| `--version` | — | print the version and exit |
| `-h`, `--help` | — | built-in help; works after a command too |

## Your token

c4mpus identifies you with a **JWT** — a long string your browser receives when you
log in, which works like a temporary key. `cyl login` saves it to `~/.c4mpus_token`
with mode `600`, readable only by your own user account.

**Your token is stored locally and goes nowhere else.** It stays on your machine, is
sent only to `api.c4mpus.com` as the `Authorization` header on your own requests, and
is transmitted to no one else — there is no cyl server, no telemetry, and no third
party anywhere in the path. The browser snippet that lifts it out of your session
sends nothing either; it copies the token to your clipboard and stops there. Treat it
like a password: it *is* access to your account.

cyl looks for one in this order, first found wins:

| Source | Notes |
| --- | --- |
| `--token '<jwt>'` | one-off, highest priority |
| `$CYL_TOKEN` | handy for a script or shell function |
| `$C4MPUS_TOKEN` | alias for the same thing |
| `~/.c4mpus_token` | what `cyl login` writes, mode `600` |

Every run shows you the clock, and an expired token is discarded automatically:

```
  ✓ Jane Doe (123456)  token valid 6d 17h · until 22 Oct 15:02
```

```bash
python3 cyl.py logout      # deletes ~/.c4mpus_token on this machine only
```

**`logout` is housekeeping, not revocation.** A JWT stays valid until its own expiry
no matter what you delete locally. **To actually kill one, log out of c4mpus in your
browser** — that expires it immediately, everywhere.

## Limits

- **A module listed in two years** is attributed to the first year it appears in.
- **cyl marks lessons, not assessments.** Coursework is untouched; the dashboard only
  counts it so you know it's there.

## Disclaimer

cyl is an unofficial client. It is not affiliated with, endorsed by, or supported by
c4mpus, or by any institution that uses it.

It is intended for use with your own account and your own enrolment. You are
responsible for ensuring that your use of it complies with your institution's academic
integrity policy and with the c4mpus terms of service. Running it against an account
you do not own, or using it in any way those rules forbid, is unauthorised use.

**Responsibility for how this tool is used rests entirely with the person using it.**
The repository owner and contributors accept no liability for any loss, damage,
academic penalty, or other consequence arising from its use or misuse, in any case.
The software is provided "as is", without warranty of any kind — see
[LICENSE](LICENSE).

## License

Licensed under the [Apache License 2.0](LICENSE) — Copyright 2026 saradk5.

You may use, modify and redistribute cyl, including commercially, provided you retain
the license and copyright notice and state any significant changes you made. It is
distributed **without warranty of any kind**: sections 7 and 8 of the license disclaim
warranty and limit liability in full.

## Requirements

Python 3.8 or newer, and nothing else — `http.client`, `ssl`, `json` and
`concurrent.futures` are all standard library. On python.org builds for macOS, which
ship without a usable trust store, cyl falls back to `certifi` if it's installed.

Optionally, drop the `python3`:

```bash
chmod +x cyl.py
./cyl.py
```

## Thank You

Thanks for checking out cyl. Feedback and contributions are always welcome.
