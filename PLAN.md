# Kobo-FOMO: Project Plan

> **Motto:** Plan twice, code once.
> **Status:** Phases 0–1 done. Phase 2 (feasibility spikes) in progress: Spike A done, Spike C (converters) next.
> **Last updated:** 2026-10-23

## 1. Vision

Turn an old **Kobo Glo** into a calm, distraction-free reader that works for my eyes:
my own books and my documents, all in **bold-start lettering**.
It has no store, no Kobo account, and no bloat.

## 2. The device

| Item | Value |
|---|---|
| Model | Kobo Glo (N613, released 2012) |
| Firmware | **2.1.5** (factory restore on 2026-10-23; previously 4.26.16704) |
| Screen | 6″ e-ink, 1024×758, touch, front light |
| Storage | 2 GB internal (plus a microSD slot) |
| Network | Wi-Fi (MAC recorded privately, not in this repo) |
| Operating system | Linux, running Kobo's reading app ("Nickel") |

## 3. Requirements

Each requirement has an ID so that features, tests and decisions can point back to it.
IDs are never reused or renumbered; dropped requirements are crossed out.
Priority is **Must**, **Should** or **Could**, a simplified "MoSCoW" ranking.

| ID | Requirement | Priority |
|---|---|---|
| R1 | No Kobo store, no Kobo account, no contact with Kobo servers | Must |
| R2 | Read my own EPUB files | Must |
| R3 | **Bold-start lettering** (bionic-style) on everything I read, to help with Irlen syndrome | **Must** |
| R4 | ~~Themed reading styles~~ | Removed (2026-10-23): not needed; the Glo's built-in settings are enough |
| R5 | Documents in these formats can be put on the reader: Google Docs (downloaded as `.docx`), Word `.docx`, LibreOffice/OpenOffice `.odt`, text-based `.pdf`, `.txt`, Markdown `.md` | Should |
| R6 | ~~News feeds by region and topic search~~ | Removed (D5) |
| R7 | ~~News filtering~~ | Removed (D5) |
| R8 | **Push:** new and changed files go from a folder on my computer to the reader over USB. Sync never deletes anything from the reader; I delete books on the reader myself | Must |
| R9 | No bloat: only the features listed here | Must |
| R10 | **Pull:** copy a document from the reader back to my computer, without the bold-start formatting | Should |
| R11 | **More fonts:** traditional press (serif) fonts and more sans-serif fonts, each with a real **Bold** (bold-start depends on it). Open-licensed only | Should |
| R12 | **Custom sleep screen:** our own graphic when the Kobo is asleep or powered off | Should |
| R13 | **Custom power-on screen:** our own graphic in the boot animation | Could |

### Out of scope (deliberately not doing)

- **Libby / library loans.** They are locked with Adobe DRM, which our reader can't open and
  which can't be converted to bold-start text. (Decision D2.)
- **News / RSS feeds.** (Decision D5.)
- **Automatic two-way sync.** (Decision D6.)
- **Scanned PDFs** (images of text). They would need OCR (text recognition); only PDFs with selectable text are supported.
- Games, the Kobo store, social features, cloud accounts.
- Writing a reading app from scratch. (Decision D1.)

## 4. Decisions

Each decision is recorded with *why* it was made, so we don't relitigate it later.
(Professionals call these "Architecture Decision Records", or ADRs.)

| ID | Decision | Why |
|---|---|---|
| ~~D1~~ | ~~Use **KOReader** (open source) as the reading app instead of building one~~ (superseded by D13) | It supports the Glo, has no store, and has 10+ years of community work. We spend our effort on what makes it *ours* |
| D2 | **No Libby** on the device | DRM conflicts with R1 and R3, and removing DRM breaks loan terms and the law. Simplicity wins |
| D3 | Name the feature "bold-start" (or a name we choose), not "Bionic Reading" | "Bionic Reading" is a trademark of its inventor's company |
| D4 | **"Smart computer, simple reader."** All conversion happens on the computer, and the Kobo only displays the results | The computer is about 50× faster, easier to test on, and can't be bricked |
| D5 | **No news feature** | Not needed. Keeps the project focused on reading |
| D6 | Sync is two **separate, manual commands**: `push` (adds and updates only) and `pull` (on request). There is no automatic two-way sync | Automatic two-way sync has to resolve "conflicts", when both sides changed. Two simple commands do what you need with no surprises |
| D7 | Bold-start formatting is **reversible**: our bolding is tagged with a unique marker so it can be removed exactly | Makes `pull` (R10) return clean text, and never confuses our bold with the book's own bold |
| D8 | The bold-start engine is a **separate, reusable library** that knows nothing about Kobos | So the future desktop app (P1) can reuse it as-is. This is called "separation of concerns" |
| D9 | No full device backup (your call, since your risk tolerance is "adventurous"). Before editing any single file on the Kobo, we still save a copy of it first | The Glo has a factory reset as the recovery path, and copying individual files costs nothing |
| D10 | Install firmware **4.38.23429** (Aug 2025, the Glo's newest) **by hand over USB**, never over Wi-Fi | Modern KOReader launchers (NickelMenu) need 4.6+; 4.31+ has "sideloaded mode" to hide the store; it's already the latest, so the Kobo has nothing to auto-update to |
| D11 | GitHub repo is **public** (GPL-3.0), not private | It's a portfolio piece showing how AI can support accessibility. Nothing personal is ever committed (see `CLAUDE.md`, Privacy) |
| D12 | Every EPUB the pipeline outputs **must include an EPUB 2 `toc.ncx`** (adding one if the source book lacks it), and is checked automatically before it's copied | Spike A proved a missing `toc.ncx` freezes Kobo's Adobe-based reader when settings change |
| D13 | Use **Kobo's built-in reader** (in Sideloaded Mode); KOReader is parked (P2) | After Sideloaded Mode (R1 ✅) and Spike A, the built-in reader does everything needed so far. "YAGNI": don't add complexity until it's needed |
| D14 | *Pending Spike C:* choose the converter. Option 1: **Pandoc** for documents plus a PDF tool. Option 2: **Calibre** for everything | Decided by comparing real output on the Kobo, not by guessing |
| D15 | Change only the boot **animation** frames (`/etc/images/kraken-on-*.raw.gz`), never the bootloader's first logo | Replacing animation images can't stop the Kobo from starting, and is easy to undo. The bootloader logo lives in a raw area where a mistake could brick the device |

## 5. Architecture

```
   YOUR COMPUTER                                         KOBO GLO
 ┌──────────────────────────────────────────┐        ┌───────────────┐
 │  Inbox/            Pipeline (Python)     │        │               │
 │  ├─ my EPUBs  ──►  1. convert to EPUB    │  push  │   KOReader    │
 │  ├─ Google Docs    2. bold-start         │ ─────► │               │
 │  └─ PDFs           3. copy new/changed   │        │  no Kobo      │
 │                                          │        │  store or     │
 │  Pulled/      ◄──  un-bold               │ ◄───── │  account      │
 │                    (exact original text) │  pull  │               │
 └──────────────────────────────────────────┘        └───────────────┘
```

- **Push:** plug in the Kobo, run `push`, unplug, read. Only adds and updates.
- **Pull:** run `pull` and pick a document. It arrives in `Pulled/` with the bolding removed.
  (A PDF comes back as the EPUB it was converted into, not the original PDF.)
- **Bold-start algorithm (first idea):** bold roughly the first 40–50% of each word's letters,
  with a strength setting we tune *on the device with your eyes*, not in theory.

### Code structure (first sketch, to be refined in Phase 3)

```
boldstart/    the reusable engine: text in → bold-start text out. Knows nothing about Kobos (D8)
kobo_sync/    Kobo-specific parts: find the Kobo, push, pull
tests/        automatic checks that the code does what we expect
```

## 6. Phases and milestones

Each phase has a **definition of done**, the test of whether we can move on.

| Phase | Work | Definition of done |
|---|---|---|
| 0. Discovery ✅ | Get USB working, record device details | The computer sees the Kobo and its details are recorded |
| 1. Requirements ✅ | This document | You approve sections 3–5 (approved 2026-10-23) |
| 2. Feasibility spikes | A ✅ bold-start on the Glo's screen; C: compare converters on real sample files for each format (B, KOReader, parked by D13) | Each risky unknown is answered "yes", "no" or "yes, but…" |
| 3. Design | Folder layout, config file format, how the pipeline steps connect | Written design you understand and approve |
| 4. Setup | git repo, public GitHub repo `Kobo-FOMO` (started early), Python project, tests | Empty but working project skeleton on GitHub |
| 5. Build | One feature at a time, in order: push → bold-start → Docs/PDF → pull → themes | Each feature tested on the Kobo before starting the next |
| 6. Lock-down | Remove or block Kobo services, boot into KOReader | R1 verified: no Kobo traffic |

## 7. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Bricking the Kobo | Medium (accepted, D9) | Copy any file before editing it; factory reset as recovery. The Glo's OS lives on an internal microSD card that could be re-imaged as a last resort |
| A Kobo firmware update undoes our setup | **High (happened 2026-10-23)** | **No Wi-Fi** until lock-down is done. Never sign in to Kobo; block update servers. Any firmware change is done manually, by choice |
| Bad USB cable or port | Medium (happened 2026-10-23) | Use the known-good cable and port; suspect the cable first when USB misbehaves |
| Bold-start text looks bad on e-ink or a slow processor | Medium | Phase 2 spike tests it on the real screen before we build anything |
| PDF → EPUB conversion is messy | Medium | Accept "good enough" for text PDFs; leave complex PDFs as PDF |
| Bold-start isn't scientifically proven to help | Low | What matters is whether it helps *you*, so we test it with you |

## 8. Open questions

- ~~Q1–Q3 (news questions)~~: closed by D5.
- ~~Q4. Sync and deletion~~: closed by R8, R10 and D6.
- ~~Q5. GitHub repository~~: `Kobo-FOMO`, public (D11).
- ~~Q6. Firmware~~: closed by D10.

## 8b. Spike results

**Spike A: bold-start on the Glo's screen** (2026-10-23)

- ✅ **The core idea works.** Bold-start text is readable on the Glo's e-ink screen.
- ✅ **Preferred strength: Light (30%).** This becomes the default.
- ⚠️ **Issue found:** in Kobo's built-in reader, changing the font or other settings makes the sample
  book freeze and return to the Library, even after a restart.
  - Suspect A: the test file lacked an EPUB 2 table of contents (`toc.ncx`). v2 adds one.
  - Suspect B: the Glo struggles to re-lay out pages on firmware 4.38.
  - **Control test:** Project Gutenberg's *Alice* (a known-good EPUB), plus sample v2 as `.epub`
    and as `.kepub.epub` (Kobo's other engine). Each was opened, its font changed, and a page turned.
  - ✅ **Result:** all three worked perfectly; only the original v1 sample froze. **Root cause: the missing
    `toc.ncx`** (suspect A). The Glo itself is fine. The fix is now design rule D12.
- ✅ **Kobo's built-in reader handles bold-start well** once the file is correct, in both engines.

**Research for R11–R13** (2026-10-23)

- **Fonts:** copy `.ttf` or `.otf` files into a `fonts/` folder at the top of the Kobo drive, named
  `Family-Regular`, `-Bold`, `-Italic`, `-BoldItalic`. No hacks needed.
- **Sleep screen:** images in `.kobo/screensaver/` are shown when the Kobo sleeps (unofficial; reported
  working on firmware 4.37+). Needs a setting under *Energy saving and privacy*. To test on the Glo.
- **Boot animation:** the Glo (codename *kraken*) loops 6 frames, `/etc/images/kraken-on-0…5.raw.gz`,
  showing three loading dots. Format decoded from the firmware: **758 × 1024 portrait, 16-bit RGB565
  (little-endian), gzipped**. They'd be replaced via a `KoboRoot.tgz` containing only those images.
  The originals are in the firmware package, so it can be undone.

## 9. Parking lot (future ideas, not this project)

Good ideas go here so they're not lost, but they don't expand this project's scope.

- **P1. Bold-start desktop app for Ubuntu, packaged as a snap.** It reuses the `boldstart/`
  engine (D8), which is why that engine is built as a separate library from day one.
- **P2. KOReader**, if Kobo's built-in reader ever proves not to be enough. See D13.
- **P3. Automatic Google Drive sync**, instead of downloading Google Docs as `.docx` by hand.

## 10. Glossary

| Term | Meaning |
|---|---|
| ADR | Architecture Decision Record: a written note of a decision and why it was made |
| Brick | To leave a device unable to start, "as useful as a brick" |
| Conflict (sync) | When the same file changed in two places and a program must guess which one wins |
| DRM | Digital Rights Management: a lock on a file that controls who can open it |
| EPUB | The standard ebook file format; inside, it's basically a small website in a zip file |
| Feasibility spike | A small throwaway experiment to answer "can this even work?" |
| KOReader | Open-source reading app for e-readers |
| Library (code) | Reusable code that other programs build on; it isn't a program by itself |
| MoSCoW | Prioritising as Must / Should / Could / Won't |
| Nickel | Kobo's own reading software |
| Parking lot | A list of good ideas deliberately held for later |
| Pipeline | A series of steps where each one's output feeds the next |
| Push / Pull | Sending files *to* a place / fetching files *from* a place |
| Scope | What a project will and won't do |
| Separation of concerns | Splitting code so each part has one job and doesn't depend on unrelated parts |
| Snap | Ubuntu's app package format, installed with `snap install` |
| Source of truth | The one place whose copy wins if two copies disagree |

## 11. Project log

A short diary of what actually happened, so future-us knows *why* things are the way they are.

- **2026-10-23:** Project started. Device identified as a Kobo Glo (not a 2010 model). Plan drafted.
- **2026-10-23:** The Kobo joined Wi-Fi and started an automatic update. It was powered off mid-update
  and got stuck in a boot loop. A factory reset (light button + power switch) restored firmware 2.1.5
  and rebuilt the storage area. The USB connection was still dropping until a new cable and port were
  used. **Lessons:** keep the Kobo off Wi-Fi; suspect the cable first. Phase 0 done.
- **2026-10-23:** Skipped Kobo account setup: added an offline placeholder user (`kobo-fomo-offline`)
  to `.kobo/KoboReader.sqlite`. A copy of the original is in `backups/2026-10-23-after-factory-reset/`.
- **2026-10-23:** Firmware 4.38.23429 downloaded from Kobo, checksum verified, copied to `.kobo/`, and
  re-verified from the device after a remount. The `.kobo` folder was backed up first to
  `backups/2026-10-23-before-fw-4.38/`. Install started.
- **2026-10-23:** Firmware 4.38.23429 installed. The screen was black with stripes for about 5 minutes
  with no light, then the Kobo booted on its own. **Lesson: during an update, a black or striped screen
  means wait.** Nickel then showed "You haven't synced your eReader". Added `SideloadedMode=true` to
  `[ApplicationPreferences]` in `.kobo/Kobo/Kobo eReader.conf` (backup in
  `backups/2026-10-23-before-sideloaded-mode/`).
- **2026-10-23:** The firmware rejected the placeholder user ("critical error"), so we tapped **Sign out**,
  which reset the Kobo to setup. Re-added `SideloadedMode=true`, then **restarted** the Kobo. It went
  straight to the home screen with no account and no pop-ups. **Lesson: the Kobo reads its settings
  file only at startup, so restart after editing it.** R1 (no Kobo account) is achieved.
