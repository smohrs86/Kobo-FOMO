# kraken: Design

> **Status:** **APPROVED** 2026-10-23, with every recommendation in section 12 accepted (D24–D26). Nothing is built yet.
> **Scope:** the owner's own tool, run from source on their computer (D23). Snap and public release come later.
> **Source of truth for *what* and *why*:** `PLAN.md`. This file is the *how*.

## 0. The short version

1. You move files to read into **`~/KRAKEN/`**.
2. You plug in the Kobo and tap *Connect*.
3. kraken notices the Kobo, then for each waiting file: **converts** it to an EPUB, adds **bold-start**,
   **checks** it, **copies** it to the Kobo, **verifies** the copy, and moves the original to `~/KRAKEN/sent/`.
4. It syncs your chosen **fonts**, **ejects** the Kobo safely, and shows a **notification**: "3 sent, 1 skipped".
5. You unplug and read.

It has four commands: `kraken push`, `kraken pull`, `kraken fonts` and `kraken autosync`. That's the whole
tool.

At the end (section 12) there are **three small questions** for you, each with a recommended answer.

---

## 1. Folders

### On the computer

```
~/KRAKEN/                  your inbox: drop files here to send them
├── as-is/                 files sent unchanged: no conversion, no bold-start (PDF ladder step 2, D21)
├── sent/                  originals of everything already sent (D22)
├── skipped/               files kraken couldn't use, each with a short note saying why
└── pulled/                documents pulled back from the Kobo, bold-start removed (R10)

~/.config/kraken/settings.toml    your settings (section 4)
~/.local/state/kraken/kraken.log  a diary of what kraken did, for when something goes wrong
~/.local/share/kraken/fonts/      the font catalogue that `kraken fonts` picks from (section 7)
~/.local/share/kraken/font-picks.json   the families you ticked in `kraken fonts`
```

Why these places? Linux has a convention (the **XDG Base Directory** standard) saying settings go in
`~/.config`, program data in `~/.local/share`, and logs in `~/.local/state`. Following it means your home
folder stays tidy, and other Linux users will find things where they expect them. Only `~/KRAKEN/` is out in
the open, because it's the one folder you use by hand.

**Rules:**

- Push only looks at files sitting directly in `~/KRAKEN/` and `~/KRAKEN/as-is/`. Sub-folders like `sent/`
  are never sent again. That's how a book you deleted on the Kobo stays deleted (D22).
- A file moves to `sent/` only **after** its copy on the Kobo is verified. If anything fails, it stays put
  and is tried again next time.
- A file that *can't* work (a scanned or password-locked PDF, an unknown file type) moves to `skipped/` with
  a note, so it isn't retried, and failed, on every plug-in.
- To update a document, drop the new version in `~/KRAKEN/` again. It replaces the old one on the Kobo and in
  `sent/`.

### On the Kobo

```
KOBOeReader/
├── kraken/                every book kraken sends
├── fonts/                 fonts (the Kobo looks for them here; R11)
├── .kraken/manifest.json  list of every font kraken installed (D18)
└── .kobo/                 Kobo's own system folder: kraken NEVER writes in here
```

- **Book names** are worked out from the original filename: `research-report.docx` becomes
  `kraken/research-report.epub`. Because the name can always be worked out again, kraken doesn't need to keep
  a list of the books it sent. If two waiting files would get the same name (`report.docx` and `report.pdf`),
  the second one waits and kraken tells you.
- **The manifest** is a small file listing the fonts kraken installed. It lives on the Kobo because it
  describes what's *on the Kobo*. The dot at the start of `.kraken` hides the folder, and the Kobo doesn't scan
  hidden folders for books (*to verify on the device*).
- **Output format: plain `.epub`**, not `.kepub.epub`. Spike A showed both work, but `.epub` is the standard
  format, it's what we tested the `toc.ncx` fix with (D12), and it keeps `pull` simple. We can try `.kepub` later
  if page turns feel slow.

---

## 2. The pipeline: what happens to each file

A **pipeline** is a series of steps where each step's output feeds the next. Every file goes through this:

```
 ~/KRAKEN/file
      │
      ▼
 1. IDENTIFY   by its extension: .epub .docx .odt .pdf .txt .md (anything else → skipped/)
      │
      ▼
 2. CONVERT    to EPUB (EPUBs skip this step). PDFs use the ladder below
      │
      ▼
 3. TIDY       fill in a missing title (Q9), add toc.ncx if it's missing (D12)
      │
      ▼
 4. BOLD-START the boldstart/ engine, at your strength setting
      │
      ▼
 5. CHECK      is it a valid EPUB? does toc.ncx exist? (a broken book never reaches the Kobo)
      │
      ▼
 6. COPY       to the Kobo as "name.epub.kraken.part", flushed to the device
      │
      ▼
 7. VERIFY     read the copy back from the device; its hash must match the original.
               Only then rename it to "name.epub"
      │
      ▼
 8. FILE IT    move the original to ~/KRAKEN/sent/
```

**Why copy as `.part` and then rename?** Copying takes time; renaming is instant. So if the cable drops
halfway through, all that's left is a `.part` file the Kobo ignores, never a half-finished book. Renaming
happens all at once or not at all, which programmers call an **atomic** operation. kraken deletes leftover
`.part` files the next time it runs. The ending is kraken's own, `.kraken.part`, so it can't mistake
someone else's `.part` file for one of its leftovers.

**Why "read back from the device"?** Linux keeps recently written data in memory (the **page cache**), so a
plain read-back would check memory, not the Kobo. After flushing (`fsync`), kraken asks Linux to drop its
memory copy of the file (`posix_fadvise`), so the check reads what actually reached the Kobo.

**Titles (Q9):** the Kobo's library shows a book's *metadata* title, not its filename. If a document has no
title, kraken uses its first heading, and if it has no headings either, its filename (`research-report` →
"Research Report").

**Files in `as-is/`** skip steps 2–5. They're copied, verified and filed just the same.

### The PDF ladder (D21)

| Step | What kraken sees | What happens |
|---|---|---|
| 1 | A PDF with real text in it | Converted to EPUB with bold-start, like any other file |
| 2 | *You* decide the converted version looks bad on the Kobo | Delete it on the Kobo, then move the PDF from `sent/` to `as-is/`. Next push sends the original PDF unchanged |
| 3 | A PDF with no text (a scan) or a password lock | Moved to `skipped/` with a note saying why |

Step 2 is your eyes, not kraken guessing. Writing code that judges whether a layout "looks bad" is hard to get
right. You can judge it in a second.

---

## 3. Commands

| Command | What it does |
|---|---|
| `kraken push` | Runs the pipeline on everything waiting, syncs fonts, ejects, notifies |
| `kraken push --dry-run` | Shows what push *would* do, without doing anything (yes, it's named after today's walkthrough) |
| `kraken push --rebuild` | Re-bolds the books still on the Kobo at your current strength, from their copies in `sent/` |
| `kraken pull` | Lists the books kraken put on the Kobo; you pick one; it lands in `~/KRAKEN/pulled/` without bold-start |
| `kraken fonts` | A checklist of the fonts in the catalogue; your picks are installed or removed on the next push |
| `kraken autosync on` / `off` | Turns automatic push-on-plug-in on or off (section 6) |
| `kraken autosync` | Says whether auto-sync is on or off (D42) |

`--rebuild` only touches books **still on the Kobo**, so it can't bring back books you deleted.

**Two krakens at once:** if you run a command by hand while auto-sync is watching, they could step on each
other. So whichever starts first takes a **lock**: a small file that means "busy, wait your turn". For example,
run `kraken pull` before plugging in. It says "plug in the Kobo now", and auto-sync stands back while it works.

---

## 4. Settings

One file, `~/.config/kraken/settings.toml`. **TOML** is a simple settings format meant to be read and edited
by people. kraken creates it with these defaults the first time it runs:

```toml
# kraken settings. Lines starting with # are notes and are ignored.

[boldstart]
# Fraction of each word's letters in bold. 0.30 = Light, your pick from Spike A.
strength = 0.30

[folders]
inbox = "~/KRAKEN"

[autosync]
eject_after_push = true    # eject the Kobo safely when push is done
notify = true              # show a desktop notification with the results
```

That's deliberately short (R9, no bloat). Your font picks are stored separately, in kraken's own data folder,
because the picker writes them and settings are for you to edit.

---

## 5. The bold-start engine (`boldstart/`)

This is the heart of the project. It's a separate **library** (reusable code that other programs build on) that
knows nothing about Kobos (D8), so a future desktop app (P1) can reuse it as-is.

**What it offers:**

```python
bold_text(text, strength)                 # one piece of text → bold-start HTML
bold_epub(source, destination, strength)  # a whole EPUB → a bold-start EPUB
unbold_epub(source, destination)          # undo it exactly (D7), for pull
```

**How it works on a book:** an EPUB is a zip file full of small web pages (**XHTML**). The engine opens each
page with **lxml**, a well-tested library for reading and writing web pages and XML, and visits every piece of
text. It never treats a page as a plain string of text, so it can't break the page's markup.

**What gets bold-start, and what doesn't (Q9):**

| Bolded | Left alone |
|---|---|
| Ordinary text: paragraphs, lists, tables, quotes, footnotes | Headings (already bold) |
| | Text that is already bold or `<strong>` |
| | Code (`<code>`, `<pre>`) |
| | Web addresses and email addresses |

**Improvements over the spike:**

- **Every alphabet's letters count.** The spike only recognised A–Z, so "café" or "naïve" broke apart. The
  engine will treat accented letters as letters.
- **No double-bolding.** If a book already has our marker (from an earlier run, or from `--rebuild`), the
  engine removes it first, then applies bold-start again at the new strength.
- **Unique marker (D7).** Our bold is `<b class="kraken-bs">`. The spike used `bs`, which some book could
  plausibly use for its own reasons.

**The promise, and the test that guards it:** `unbold_epub(bold_epub(book))` gives back exactly the original
text. If that test ever fails, `pull` would be returning a damaged document.

---

## 6. Auto-sync on plug-in (R14)

**The problem:** something has to notice "the Kobo just connected" and run `kraken push`.

**The plan:** a **systemd user service**. systemd is the part of Ubuntu that starts and looks after background
programs. A *user* service runs as you, not as the all-powerful administrator account (root), and starts when
you log in. It runs `kraken autosync watch`, which checks every 3 seconds whether a drive named `KOBOeReader`
has appeared. Checking at intervals like this is called **polling**. It's the simplest reliable approach and
uses almost no power.

`kraken autosync on` writes the service's small settings file (a **unit file**) and switches it on, so you
never have to edit system files by hand.

**When the Kobo appears:** wait for the drive to settle → `kraken push` → eject safely
(`udisksctl unmount`, then `udisksctl power-off`, the same steps you already use by hand) → notification
(`notify-send`). The Kobo then shows its "you can unplug" state, and you unplug.

**The details (approved 2026-10-24, D37–D42):**
- **Settled** = seen mounted on two checks in a row (D37).
- **Once per plug-in:** after a push, the watcher waits for the Kobo to disappear and come back (D38).
- **No retries:** a failed push is reported by notification, and the next plug-in tries again (D39).
- **Busy:** if kraken is already running by hand, the watcher steps aside for that plug-in (D40).
- **Already there at start:** a Kobo that's connected when the watcher starts is pushed (D41).
- **The unit file** is `~/.config/systemd/user/kraken-autosync.service`. It runs the venv's
  `kraken autosync watch`, restarts it if it crashes, and starts at log-in. `off` switches the service off
  and deletes the file. Running `on` again rewrites the file and restarts the service, so it also fixes a
  moved venv.
- **Risk to check at Checkpoint B:** a background service isn't quite inside the desktop session, so the
  notification and the eject (polkit, Ubuntu's permission system) may behave differently from a terminal.
  If the eject is refused, the notification says so and you eject from the file manager.

**Alternatives considered:**
- A **udev rule** (Linux's hardware-event system) would react instantly, but it runs as root and before the
  drive is even mounted. More power, more risk.
- Listening for **D-Bus** messages from udisks (the desktop's own "a drive appeared" announcements) is the
  most elegant option, but it's more code for no gain you'd notice.

---

## 7. Fonts (R11)

- **The catalogue** is `~/.local/share/kraken/fonts/`, which holds open-licensed font families, each with at
  least a Regular and a real Bold, plus its licence file. To start with, we download a starter set together,
  check each one's licence, and keep the separate **static** files (one file per weight), because Kobo's support
  for **variable** fonts (all weights in one file) is uncertain.
  (Checkpoint A: a variable font did appear in the menu and display at its default weight; other weights
  weren't tested.)
  Candidates: **Atkinson Hyperlegible** (already downloaded), **Literata** (designed for e-reading),
  **Lexend** (designed for reading ease), **Andika** (designed for clear letter shapes).
- **Catalogue layout:** one folder per family, named as it appears in the checklist. Each file's style
  comes from the end of its name (`-Regular`, `-Bold`, `-Italic`, `-BoldItalic`); other weights are ignored.
  A family is left out, with the reason shown, if it has no Regular, no Bold, no licence file (a name
  starting `OFL`, `LICENSE` or `LICENCE`), two files for one style, or a "font" that isn't one (checked
  by the file's first four bytes, which catches a web page saved by mistake). A family with no `-Italic`
  is kept, but the checklist warns that the Kobo will show its italic text as bold (D36).
  ```
  ~/.local/share/kraken/fonts/
  ├── Atkinson Hyperlegible/   AtkinsonHyperlegible-Regular.ttf, AtkinsonHyperlegible-Bold.ttf, OFL.txt
  └── Literata/                Literata-Regular.ttf, -Bold, -Italic, -BoldItalic, OFL.txt
  ```
- **`kraken fonts`** shows a checklist of the families in the catalogue. Ticked = install on the Kobo.
- **On the next push,** kraken copies ticked families into `fonts/` on the Kobo, renamed to the Kobo's
  pattern (`Family-Regular.ttf`, `-Bold`, `-Italic`, `-BoldItalic`). It removes unticked families **only if the
  manifest says kraken installed them** (D18). Fonts you added by hand are never touched.
- **The manifest** (`.kraken/manifest.json` on the Kobo) lists each font file kraken installed, with its
  family and SHA-256 fingerprint, so unchanged fonts aren't copied again. It's saved **before** copying, with
  new files marked *pending* (blank fingerprint), and again after. If a sync is cut off halfway, the pending
  entries still claim those names as kraken's, so the next push finishes the job instead of mistaking
  kraken's own files for hand-added ones. (Databases call this idea a **write-ahead log**.) A damaged
  manifest stops the font sync rather than guessing.

---

## 8. Safety rules built into the code

These turn `CLAUDE.md`'s device rules into checks the code makes every time:

1. **Is this really the Kobo?** Before writing anything, kraken checks that the drive is named `KOBOeReader`
   and has a `.kobo/` folder. If not, it stops.
2. **Never write inside `.kobo/`.** (The sleep screen is already done by hand. The boot screen, R13, gets its own
   design later, with backups.)
3. **Never delete a book.** The only things kraken ever deletes on the Kobo are fonts listed in its manifest
   and its own leftover `.kraken.part` files. The delete function itself refuses anything outside `fonts/`, so even a bug
   elsewhere can't delete a book.
4. **Enough space?** It checks free space before copying (the Glo has 2 GB) and stops with a clear message
   if there isn't room.
5. **One bad file never stops the others.** Each file succeeds or fails on its own, and the notification
   reports all of them.
6. **Nothing goes online.** kraken only reads files on your computer and writes to the Kobo.

---

## 9. Converting documents (D14, waiting on Spike C)

Each format gets its own small **converter** that follows one agreed shape, called an **interface**: take a
file in, give an EPUB back. The rest of kraken doesn't care *how* a converter does it, so we can swap Pandoc
for Calibre, or the other way round, for any format without touching anything else.

| Format | Likely converter | Notes |
|---|---|---|
| `.epub` | none | Checked and tidied only |
| `.docx`, `.odt`, `.md` | Pandoc or Calibre | Spike C decides |
| `.txt` | Pandoc, plus a clean-up step | Re-joins lines that were split at a fixed width (as in Gutenberg's `.txt` files) into proper paragraphs |
| `.pdf` | Calibre, or Poppler's `pdftotext` | Poppler is a standard PDF toolkit. Its `pdfinfo` also spots locked PDFs, and almost no extractable text means a scan |

Installed today: Pandoc 3.7, Calibre 9.2, Poppler, lxml 6.0, and `notify-send`.

---

## 10. Code layout and how to run it

```
boldstart/              the reusable engine (D8). Knows nothing about Kobos
  text.py               splitting text into words, how many letters to bold
  epub.py               bold / unbold a whole EPUB
kraken/
  cli.py                the commands (section 3)
  push.py               the steps of `kraken push`: find, plan, apply, eject, notify
  lock.py               "busy, wait your turn" (flock, D34)
  settings.py           reads settings.toml, creates it with defaults
  inbox.py              finds waiting files; files them in sent/ or skipped/
  convert.py            one converter per format, plus the PDF ladder
  checks.py             "is this EPUB safe for the Kobo?" (D12)
  kobo.py               find the Kobo, copy, verify, eject
  fonts.py              catalogue, checklist, manifest
  autosync.py           the watcher and its systemd unit file
  notify.py             desktop notifications
tests/
  fixtures/             tiny sample files we make ourselves (never personal ones)
pyproject.toml          the project's ID card: name, dependencies, and the `kraken` command
```

(`PLAN.md`'s first sketch called the Kobo part `kobo_sync/`. `kraken/` replaces it, after D16.)

**Running from source (D23):** a **virtual environment** ("venv") is a private Python installation just for
this project, so its libraries never clash with Ubuntu's own. Ubuntu leaves the venv tool out, so install it
once with `sudo apt install python3-venv`. Then setup is three commands, done once:

```bash
python3 -m venv .venv                # make the private Python
.venv/bin/pip install -e ".[dev]"    # install kraken and pytest ("-e": code edits take effect immediately)
.venv/bin/kraken --help              # the kraken command now exists
```

Run the tests with `.venv/bin/pytest`.

**Dependencies** (libraries kraken needs that aren't built into Python): **lxml** (reading book pages),
**pytest** (running tests), and maybe a small checklist library for `kraken fonts`. Everything else comes
from Python's standard library or the tools already installed.

---

## 11. Testing

**Automatic tests** (with **pytest**, which runs every function named `test_…` and reports what failed) check
everything that doesn't need the real Kobo. That's most of kraken:

- **The engine:** strength maths, accented letters, the skip rules, no double-bolding, and the round-trip
  promise (bold then unbold gives back the original).
- **EPUB checks:** a book with no `toc.ncx` gets one; a broken zip is rejected.
- **The inbox:** files move to `sent/` only after success, and to `skipped/` with a note.
- **Copying, using a fake Kobo:** a temporary folder with a `.kobo/` inside stands in for the device
  (programmers call a stand-in like this a **test double**). This tests copy, verify, `.part` clean-up, the
  font manifest, and "never delete a book" without plugging anything in.

Test files are tiny ones we write ourselves or take from the public domain. Your real books are never used.

**Device tests** are a short checklist for each feature, done with the real Glo and your eyes before the
next feature starts (Phase 5's definition of done). For example: "the font appears in the Kobo's font menu",
"the Gutenberg book opens, changes font without freezing, and the bold-start looks right".

---

## 12. Build order and the three questions

### Milestones (D17, the walking skeleton)

| # | Feature | Device test |
|---|---|---|
| 1 | **Skeleton:** settings, find the Kobo, font catalogue and checklist, copy + verify, manifest, eject, notify, auto-sync | Tick a font, plug in: it's in the font menu. Untick it, plug in: it's gone. Your own fonts are untouched |
| 2 | **Bold-start EPUBs:** the engine, the inbox for `.epub`, `sent/` | The Gutenberg book arrives in bold-start; deleting it on the Kobo, then plugging in again, does *not* bring it back |
| 3 | **Documents:** Spike C first, then converters, the PDF ladder, `skipped/`, `as-is/` | Your newsletter and research report read well |
| 4 | **Pull** | A pulled document matches the original, with no bold-start left |
| 5 | **Rebuild** | Change strength to 0.35: books on the Kobo update; deleted ones stay deleted; reading position (Q10) |
| (6) | Boot screen (R13, Could) | Gets its own design first |

### Milestone 1 steps (approved 2026-10-23, D31–D34)

Each step has its own automatic tests and its own commit. 🔌 marks a device checkpoint.

| # | Step | File | What it does |
|---|---|---|---|
| 1 | Settings | `settings.py` | XDG folders; creates `settings.toml` with defaults; clear messages for typos and bad values |
| 2 | Find the Kobo | `kobo.py` | Finds the `KOBOeReader` drive in the mount list, checks for `.kobo/` (rule 1), notes its device for ejecting |
| 3 | Safe copy | `kobo.py` | `.kraken.part` → flush → verify from the device → rename; free-space check (rule 4); refuses paths in `.kobo/` (rule 2) |
| 4 | Font catalogue | `fonts.py` | Families in the catalogue; each needs a Regular, a real Bold and a licence file |
| 5 | Sync plan | `fonts.py` | Picks + catalogue + manifest → what to install and remove. Decides only. Removes only manifest fonts (D18) |
| 6 | Apply the plan | `fonts.py` | Safe copy, then update the manifest |
| 7 | `kraken fonts` | `cli.py` | The numbered checklist (D31); picks saved in kraken's data folder |
| 8 | `kraken push` | `cli.py`, `notify.py` | Find → font sync → eject → notify; the `flock` lock and log (D34); `--dry-run` (D32) |
| 🔌 A | Device test | | Starter catalogue (D33). Tick, push, font in menu; untick, push, gone; hand-added font survives; `.kraken/` not shown as books; does the Kobo need a restart to see new fonts? **Passed 2026-10-24** (no restart needed; see PLAN.md log) |
| 9 | Auto-sync | `autosync.py` | Watcher (every 3 s), pushes **once per plug-in**; `kraken autosync on`/`off` writes the systemd unit |
| 🔌 B | Device test | | Plug in, tap *Connect*: push, eject and notification happen by themselves |

### Three questions for you (answered 2026-10-23: all recommended)

1. **Font picker:** a **checklist in the terminal** (recommended: simple, and what the rest of kraken is) or a
   small window?
2. **Auto-eject:** after auto-sync, eject the Kobo **automatically** (recommended: then you just unplug when
   the notification appears) or leave it connected?
3. **Names:** happy with `~/KRAKEN/` and its `sent/`, `skipped/`, `as-is/` and `pulled/` folders, and books in
   `kraken/` on the Kobo? (Recommended as written.)

Everything else in this file is a recommendation you can also question. Once you approve, the choices become
`D#` entries in `PLAN.md` and Milestone 1 can start.
