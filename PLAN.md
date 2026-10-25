# Kobo-FOMO: Project Plan

> **Motto:** Plan twice, code once.
> **Status:** Phases 0–1 and 3 (Design) done. Phase 2: Spikes A and D done, Spike C pending. Phase 4 (Setup) done. Phase 5 (Build): Milestone 1 done (Checkpoints A, B passed). Milestone 2: steps 1–6 built; Checkpoint C partly passed, failed on speed (big bolded files); Spike E books on the Kobo, waiting for the test.
> **Resume here:** see [section 0, Where we left off](#0-where-we-left-off).
> **Last updated:** 2026-10-24

## 0. Where we left off

*A handoff note, so any session (human or AI) can pick up where the last one stopped.
Updated at the end of every working session.*

**Session 2026-10-24 (afternoon, Checkpoint C).** The device is working: firmware 4.38.23429, Sideloaded Mode,
no Kobo account, Wi-Fi off, custom sleep screen. Milestone 1 is done; Milestone 2 steps 1–6 are built (267 tests).

**Checkpoint C so far:** ✅ two books sent by auto-sync and filed in `sent/`; ✅ real titles; ✅ 45% (D55);
✅ real headings plain (Watts's headings are styled paragraphs, so they *are* bolded); ✅ italics stay italic.
❌ **Speed:** bolded books are slow to jump to (TOC, page jump: 20–30 s), Yarrow's page turns are slow, and a TOC
jump in Yarrow **crashed** the reader. Cause, very likely: bolding makes chapter files about 5× bigger (Yarrow:
76 → 391 KB per file), past the ~260–300 KB the built-in (Adobe) reader handles well. Not yet tested: font
change without a freeze in the real books, a deleted book not coming back, a re-dropped book replacing its copy.

On the Kobo: *Alice*, the two test books in `kraken/`, and the throwaway strength test in `kraken-tests/`
(delete by hand when done), plus Spike E's five books (E1–E5) in `kraken-tests/`. `~/KRAKEN/sent/` holds the
two originals. Auto-sync is **off** (turned off to send the spike books): the owner turns it back on with
`kraken autosync on`.

**Next up, in order:**

1. **Spike E (big files): test on the Kobo.** The five books are on the Kobo in `kraken-tests/`. The owner
   follows the test steps in section 8b and fills in the table. Then decide the fix from the results.
2. Build the fix as Milestone 2 step 7, then **finish Checkpoint C** (re-send, speed, font change, delete,
   re-drop) and mark Milestone 2 done.
3. **Spike C (converters)**, then **Literata** (D33), as before.
4. After Milestone 2: decide Q13 (strength that varies) and Q14 (a GUI?).

**Tips:** `kraken fonts` waits for typing, which the `!` prompt in Claude Code can't pass on: run it in a
normal terminal, or pipe the keys in (`printf '1\n\n' | .venv/bin/kraken fonts`). Claude Code's permission
check blocks Claude from switching on the background service, so the owner runs `kraken autosync on` / `off`.

**Waiting on the owner:** nothing blocking. Unanswered: what the screen showed when the Kobo wouldn't power
down before the second reset.

**How to run it:** `.venv/bin/kraken --help`; tests with `.venv/bin/pytest`.

## 1. Vision

Turn an old **Kobo Glo** into a calm, distraction-free reader that works for my eyes:
my own books and my documents, all in **bold-start lettering**.
It has no store, no Kobo account, and no bloat.

## 2. The device

| Item | Value |
|---|---|
| Model | Kobo Glo (N613, released 2012) |
| Firmware | **4.38.23429**, installed by hand over USB (factory restores to 2.1.5 on 2026-10-23, twice) |
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
| R3 | **Bold-start lettering** (bionic-style) on everything I read, to help with Irlen syndrome. Exception: PDFs that don't convert cleanly are sent as-is (D21) | **Must** |
| R4 | ~~Themed reading styles~~ | Removed (2026-10-23): not needed; the Glo's built-in settings are enough |
| R5 | Documents in these formats can be put on the reader: Google Docs (downloaded as `.docx`), Word `.docx`, LibreOffice/OpenOffice `.odt`, text-based `.pdf`, `.txt`, Markdown `.md` | Should |
| R6 | ~~News feeds by region and topic search~~ | Removed (D5) |
| R7 | ~~News filtering~~ | Removed (D5) |
| R8 | **Push:** new and changed files go from a folder on my computer to the reader over USB. Sync never deletes anything from the reader; I delete books on the reader myself | Must |
| R9 | No bloat: only the features listed here | Must |
| R10 | **Pull:** copy a document from the reader back to my computer, without the bold-start formatting | Should |
| R11 | **More fonts:** traditional press (serif) and sans-serif fonts, each with a real **Bold** (bold-start depends on it). Open-licensed only. Picked from a list with `kraken fonts`; installed or removed on the next sync | Should |
| R12 | **Custom sleep screen:** our own graphic when the Kobo is asleep or powered off ✅ (sleep) | Should |
| R13 | **Custom power-on screen:** our own graphic in the boot animation | Could |
| R14 | **Auto-sync on plug-in:** when the Kobo is connected (after tapping *Connect*), `kraken push` runs by itself, ejects the Kobo safely, and shows a desktop notification | Should |
| R15 | **Release:** kraken is released as a **snap** on the repo's GitHub Releases page. It contains only the tool: no personal graphics, settings or books (D20) | Should |

### Out of scope (deliberately not doing)

- **Libby / library loans.** They are locked with Adobe DRM, which our reader can't open and
  which can't be converted to bold-start text. (Decision D2.)
- **News / RSS feeds.** (Decision D5.)
- **Automatic two-way sync.** (Decision D6.)
- **Scanned PDFs** (images of text). They would need OCR (text recognition); only PDFs with selectable text are supported.
- **RTF documents** (`.rtf`). Not needed by the owner. (Decision D35.)
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
| D14 | *Pending Spike C:* choose the converter. Option 1: **Pandoc** for documents plus a PDF tool. Option 2: **Calibre** for everything. (Both installed 2026-10-23) | Decided by comparing real output on the Kobo, not by guessing. Since D20, also judged on how easily it fits inside a snap (Calibre is large; Pandoc can't read PDFs) |
| D15 | Change only the boot **animation** frames (`/etc/images/kraken-on-*.raw.gz`), never the bootloader's first logo | Replacing animation images can't stop the Kobo from starting, and is easy to undo. The bootloader logo lives in a raw area where a mistake could brick the device |
| D16 | The command-line tool is called **`kraken`** (`kraken push`, `kraken pull`) | *Kraken* is Kobo's real internal codename for the Glo (the firmware's boot images are `kraken-on-*.raw.gz`). Short, memorable, and true |
| D17 | **Build order: "walking skeleton" first.** kraken's first feature is font sync (R11), which proves the core plumbing (find Kobo → copy → verify → eject → notify) before book conversion is added | Fonts need all the plumbing but none of the hard conversion work, so the riskiest *infrastructure* gets tested early on something simple |
| D18 | kraken **only removes files it installed itself** (tracked in a manifest), and never removes books (R8) | Un-picking a font should remove it, but kraken must never touch anything it didn't put there |
| D19 | Files to read are **moved by hand into a `KRAKEN` folder** in the home folder, outside the code repo. kraken never looks in Downloads | Only what you choose gets sent. Keeps personal books out of the public repo and out of the released snap |
| D20 | **End state:** once kraken works, it is released once as a snap file on GitHub Releases (R15), then the repo is **archived** (made read-only) and development stops. The owner keeps running kraken locally | The goal is a finished tool, not an ongoing service. Archiving tells visitors the project is complete |
| D22 | `KRAKEN/` is an **inbox**: after a file is copied to the Kobo *and verified*, it moves to `KRAKEN/sent/`. Push only looks at files waiting in `KRAKEN/` | A book deleted on the Kobo can't come back, because its source is no longer waiting. To update a document, drop the new version in again. This replaces the push record proposed in Q8 |
| D23 | **Owner first, public later.** Build kraken for the owner's own Glo and computer, run from source. Snap packaging and public-release questions (R15, D20, Q11, Q12) wait until it works | Get a working tool into the owner's hands before solving other people's setups. Keeps each step small |
| D24 | **`DESIGN.md` approved as drafted:** the `~/KRAKEN/` inbox with `sent/`, `skipped/`, `as-is/` and `pulled/`; books in `kraken/` on the Kobo as plain `.epub`; copy as `.part` then rename; auto-sync via a polling systemd user service; bold-start marker `<b class="kraken-bs">` | Reviewed by the owner, who accepted every recommendation |
| D25 | The `kraken fonts` picker is a **checklist in the terminal**, not a window | Simple, and matches the rest of kraken, which is all terminal commands |
| D26 | After auto-sync, kraken **ejects the Kobo automatically** (`eject_after_push = true`) | You just unplug when the notification appears. It can be turned off in settings |
| D27 | Libraries are added to `pyproject.toml` **when the code first uses them**. pytest is a `dev` extra; lxml waits for Milestone 2 | YAGNI: no dependency until there is code that needs it (R9) |
| D28 | The command line uses **argparse**, from Python's standard library | Nothing extra to install. Click is nicer but would be one more dependency |
| D29 | kraken needs **Python 3.12 or newer** | 3.12 is the oldest Python still supported on current Ubuntu releases, and it includes `tomllib` for reading `settings.toml` |
| D30 | Subcommands appear **in the milestone that builds them**, not as stubs | `kraken --help` never advertises something that doesn't work yet |
| D31 | The `kraken fonts` checklist is a **numbered list**: type a number to tick or untick, Enter to save. Built with Python's `input()` | Nothing to install (D27) and easy to test. An arrow-key menu would need a library |
| D32 | `kraken push --dry-run` is built **in Milestone 1** | The font sync plan is already worked out before anything is touched, so printing it is nearly free, and it's a safety net for the first push to the real Kobo |
| D33 | Starter font catalogue: **Atkinson Hyperlegible** (sans-serif) and **Literata** (serif). Fonts are added to the catalogue by hand, together, with licences checked | Covers both kinds R11 asks for and keeps the first device test small. More families need no code changes. kraken itself never goes online (DESIGN.md section 8, rule 6) |
| D34 | The lock and the log live in `~/.local/state/kraken/`. The lock uses **`flock`**, the operating system's file locking | If kraken crashes, the OS releases the lock by itself, so a stale "busy" lock can't get stuck |
| D35 | **RTF (`.rtf`) is not supported**; R5's list stays as it is, and `.rtf` files go to `skipped/` | The owner doesn't receive RTF files. It's a 1987 Microsoft format, no longer developed since 2008 and replaced by `.docx`. Easy to add later if needed: Pandoc, Calibre and LibreOffice all read it |
| D36 | A font family with **no Italic is still allowed**, but `kraken fonts` **warns** next to it that italic text will show as bold on the Kobo | Found at Checkpoint A: with only Regular and Bold, the Kobo used the Bold file for italic text, so emphasis looked like bold and would be confused with bold-start. A warning (not a refusal) leaves the choice to the owner |
| D37 | Auto-sync treats the Kobo as **settled** when the watcher sees it mounted on **two checks in a row** (about 3 s apart) | Gives the desktop time to finish mounting it, without a fixed guess at how long that takes |
| D38 | Auto-sync pushes **once per plug-in**: after a push it waits until the Kobo has **gone and come back** | With `eject_after_push = false` the Kobo stays mounted, and it mustn't be pushed every 3 seconds |
| D39 | A failed auto-sync push is **not retried**; the "kraken stopped" notification says why, and the next plug-in tries again | A retry loop could fail over and over in the background without anyone noticing |
| D40 | If kraken is already running by hand, auto-sync **steps aside** for that plug-in and notes it in the log | That's what the lock is for (D34); two notifications would confuse |
| D41 | A Kobo that's **already plugged in** when the watcher starts is pushed | It's almost always there because it was just plugged in |
| D42 | **`kraken autosync`** on its own says whether auto-sync is on, off, or switched on but not running | Saves remembering `systemctl` commands |
| D43 | Bold-start applies to **letters only**: numbers such as "1865" are left alone | A half-bold number reads oddly, and the eye doesn't scan numbers the way it scans words |
| D44 | A hyphen **splits** words ("daisy-chain" is two words); an apostrophe **joins** them ("didn't" is one) | Each part of a hyphenated word is a word your eye lands on; an apostrophe sits inside a single word |
| D45 | **Short words** get at least one bold letter (rounding up), as in Spike A | The owner approved this look on the Glo |
| D46 | A book containing `META-INF/encryption.xml` (usually DRM) goes to **`skipped/`** with a note, and is never opened or changed | The legal rules (D2, `CLAUDE.md`). Simplest safe rule; revisit only if a DRM-free book needs it |
| D47 | A book with **no `toc.ncx`** goes to `skipped/` with a note that it would freeze the Kobo. **Building** a `toc.ncx` (D12) waits until a real book needs one | The three test books have one, and Pandoc and Calibre add one to the EPUBs they make (Milestone 3). Changes when D12's "add one" is built, not the rule |
| D48 | **`unbold_epub` is built in Milestone 2**, with `bold_epub` | Its round-trip test proves our marker can be removed exactly (D7); it's cheap to build alongside |
| D49 | In Milestone 2, **non-EPUB files are left in `~/KRAKEN/`**, and the summary counts them as waiting for a later version | Moving them to `skipped/` would mean moving them back once Milestone 3 exists |
| D50 | Files changed in the **last 10 seconds** wait for the next push; hidden files and unfinished downloads (`.part`, `.crdownload`) are ignored | With auto-sync, a push could start while a big book is still being copied in |
| D51 | A book's name on the Kobo is `kraken/<original name>.epub`, with `\ : * ? " < > \|` replaced by `_` | The Kobo's FAT drive can't store those characters |
| D52 | The bolded copy is built in a **temporary folder** and deleted after copying; `sent/` keeps only the original | The original is what `--rebuild` and `pull` work from; a second copy wastes space |
| D53 | The note beside a file in `skipped/` is named `<file name>.why.txt`, and says what happened, when, and how to try again. Book names that differ **only in capitals** (`Alice.epub`, `alice.epub`) clash, like D51's replaced characters; `sent/` keeps one original per name on the Kobo | Chosen while building step 5 (the design didn't name the note). The Kobo's FAT drive treats upper and lower case as the same name, so two such books would overwrite each other |
| D54 | A Kobo-format book (`Alice.kepub.epub`) loses its `.kepub` on the Kobo: `kraken/Alice.epub` | The Kobo reads a `.kepub.epub` with its own Kobo-format reader, but kraken's bolded copy is a plain EPUB (`DESIGN.md` section 1). The owner chose this on 2026-10-24 |
| D55 | Default bold-start **strength is 0.45** (Medium), up from Spike A's 0.30 | At Checkpoint C the owner compared 30/40/45/50/60% on the Glo (one test book, same text at each strength) and liked anything from 30% to 60%, depending on the font and size. 45% sits in the middle. How to vary it is open (Q13) |
| D56 | **No Wi-Fi sync: books go over USB only.** To spare the Kobo's micro-USB socket, use a **data-capable magnetic adapter** that stays in the socket while the cable snaps on and off | The owner worried that frequent plugging would wear out the socket. The socket is rated for about 10,000 plug-ins, and the parts that wear are in the cable. Wi-Fi would break R1 and risk another auto-update, and Kobo's built-in reader can't receive files over Wi-Fi without a Kobo account, firmware mods or KOReader. Even an offline hotspot (the safest version) wouldn't spare the socket, because the Kobo still charges through it |
| D21 | **PDF ladder:** (1) a text PDF becomes an EPUB with bold-start; (2) if the converted layout is poor, the original PDF is sent as-is, readable but without bold-start; (3) scanned or locked PDFs are skipped, with a message saying why. Whole classes of PDF may be dropped | Newsletters are usually text-based PDFs made to be machine-readable. Reading something without bold-start beats not reading it, and clever layout detection isn't worth building. How step 2 is chosen: `DESIGN.md` |

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

- **Push:** plug in the Kobo, run `kraken push`, unplug, read. Only adds and updates.
- **Pull:** run `kraken pull` and pick a document. It arrives in `Pulled/` with the bolding removed.
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
| 3. Design ✅ | Folder layout, config file format, how the pipeline steps connect | Written design you understand and approve |
| 4. Setup ✅ | git repo, public GitHub repo `Kobo-FOMO` (started early), Python project, tests | Empty but working project skeleton on GitHub |
| 5. Build | One feature at a time (D17): font sync + auto-sync skeleton ✅ (Milestone 1, 2026-10-24) → bold-start → document conversion → pull → boot screen | Each feature tested on the Kobo before starting the next |
| 6. Lock-down | Remove or block Kobo services, boot into KOReader | R1 verified: no Kobo traffic |
| 7. Release | Build the snap, attach it to a GitHub release (R15), archive the repo (D20) | The snap installs on a clean Ubuntu and contains no personal files; repo archived |

## 7. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Bricking the Kobo | Medium (accepted, D9) | Copy any file before editing it; factory reset as recovery. The Glo's OS lives on an internal microSD card that could be re-imaged as a last resort |
| A Kobo firmware update undoes our setup | **High (happened 2026-10-23)** | **No Wi-Fi** until lock-down is done. Never sign in to Kobo; block update servers. Any firmware change is done manually, by choice |
| Bad USB cable or port, or a worn micro-USB socket | Medium (cable failed 2026-10-23) | Use the known-good cable and port; suspect the cable first when USB misbehaves. A data-capable magnetic adapter spares the socket (D56) |
| Bold-start text looks bad on e-ink or a slow processor | Medium | Phase 2 spike tests it on the real screen before we build anything |
| PDF → EPUB conversion is messy | Medium | The PDF ladder (D21): convert if clean, otherwise send as-is, skip scanned or locked PDFs |
| Snap restrictions block USB access, auto-sync or notifications | Medium | Deferred by D23. When release work starts, package the simplest feature first, so problems show up on something small |
| Personal files leak into the released snap | Medium | Build the snap from a fresh `git clone`, never the working folder (which holds git-ignored personal files), and list the snap's contents before release |
| Bold-start isn't scientifically proven to help | Low | What matters is whether it helps *you*, so we test it with you |

## 8. Open questions

- ~~Q1–Q3 (news questions)~~: closed by D5.
- ~~Q4. Sync and deletion~~: closed by R8, R10 and D6.
- ~~Q5. GitHub repository~~: `Kobo-FOMO`, public (D11).
- ~~Q6. Firmware~~: closed by D10.

*From the scenario walkthrough (2026-10-23): a Gutenberg EPUB, a PDF newsletter and an AI-written `.docx`
pushed through the plan on paper.*

- ~~**Q7.** Does a sent file stay in `KRAKEN/` or move to a "sent" folder?~~ Closed by D22: it moves to `sent/`.
- ~~**Q8. Push record**~~ (a hash of each sent file, so deleted books aren't re-sent): no longer needed, see D22.
  Still to design: changing the bold strength re-sends nothing unless you run `kraken push --rebuild`, which
  re-bolds, from `sent/`, only the books that are still on the Kobo.
- **Q9. Design details:** a document's title when its metadata has none (proposal: its own title, else first
  heading, else filename); text bold-start skips (proposal: headings, code, web addresses); one bad file must not
  stop the others, and the notification sums up what was sent and skipped; destination folder on the Kobo;
  `.epub` or `.kepub.epub`; tell users to download Gutenberg's EPUB, not its `.txt` (hard line breaks).
- **Q10. Device test:** does re-sending an updated file keep the reading position?
- **Q11. Should kraken be fully offline?** A snap that doesn't ask for network permission *cannot* go online,
  which would enforce R1 for kraken itself. Fonts (R11) would then be bundled inside the snap.
  *Owner (2026-10-23):* going online is OK if it's limited to a public, open-licensed font library. A snap's
  network permission is all-or-nothing, so that limit would be a rule in kraken's code, not enforced by Ubuntu.
  The alternative is a curated font set bundled in the snap. Still open.
- **Q12. Which Kobos does the released kraken support?** Nothing it does needs custom firmware. Converting
  and bold-start produce standard EPUBs that any EPUB reader can open. Pushing and fonts should work on any Kobo,
  the sleep screen on recent firmware, but the boot screen (R13) is Glo-only and the riskiest feature. Only the
  Glo can be tested here.
- **Q13. Strength that varies with font and size.** The bolding is baked into the book when it's sent, and Kobo's
  built-in reader can't change it. Options: (a) one default, changed with `--rebuild` (Milestone 5); (b) a strength
  per book, for example a `~/KRAKEN/60/` folder; (c) change it on the Kobo, which needs KOReader style tweaks
  (reopens D13 and P2; needs a spike). Decide after Milestone 2.
- **Q14. A window (GUI) for kraken?** D25 chose terminal commands; the owner asked on 2026-10-24 whether there
  will be a UI to manage fonts, bold-start options and the kraken folders. Today: `kraken fonts`, `settings.toml`
  in a text editor, and `~/KRAKEN/` in the file manager. A GUI would be a new requirement, designed first.
  Decide after Milestone 2.

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

**Spike D: custom sleep screen** (2026-10-23)

- `spikes/screens/make_screen.py` builds a 758 × 1024, 16-grey sleep screen: a framed picture, a
  bold-start title (30%, Atkinson Hyperlegible), an optional emoji (Noto Emoji, black and white), and a footer
  where `**marked**` words are bold. Personal images and text are passed in at run time and stay in `personal/`.
- ✅ **Works on the Glo (firmware 4.38).** It needs **both** settings under *Energy saving and privacy*:
  **"Show current read" ON** and **"Show book covers full screen" ON**. With "Show current read" off,
  the Kobo shows a blank "Sleeping" screen. PNG (greyscale) works; JPEG wasn't needed.
- **It also needs a book in progress.** With no books on the Kobo, it showed "Sleeping" even with both
  settings on; after opening a book, the graphic appeared (confirmed 2026-10-23 after the second reset).
  The image takes the place of the current book's cover, so with no current read there is nothing to replace.
- Only one image is kept in `.kobo/screensaver/`: with several, the Kobo picks one at random.

**Spike E: why bolded books are slow** (2026-10-24, built; Kobo test pending)

- **Question:** is it the bytes per chapter file, or the number of elements (tags) per file? Bolding grows both.
  Watts's bolded files are only 174 KB, *under* the ~260 KB limit, yet its jumps were also slow, so bytes
  alone may not be the cause. A memory setting isn't an option: there's no known one for the Adobe engine,
  and swap would mean changing system files on the Kobo.
- `spikes/big-files/make_variants.py` builds five versions of Yarrow at 45%, each with its own title.
  Measured, for the largest chapter file:

  | Version | Largest file | Elements in it | Tests |
  |---|---|---|---|
  | E1 plain | 75 KB | 152 | control |
  | E2 bolded as now | 391 KB | 13,085 | the slow case |
  | E3 bare `<b>` (test only: breaks D7) | 164 KB | 13,085 | bytes |
  | E4 split by Calibre (`--flow-size=20`), then bolded | 93 KB | 3,107 | amount per file |
  | E5 E2 as `.kepub.epub` | 391 KB | 13,085 | the Kobo's own reader |

  E4: Calibre also adds a cover and renames CSS classes; all 42 TOC entries still resolve. If E4 wins,
  our own splitter confirms it in step 7.
- **Test steps.** Restart the Kobo first. For each book: open it once and wait for the page count; then,
  with a phone stopwatch, time a TOC jump to the last chapter, a page jump to about 75%, and 10 page turns;
  note any crash. Test **E2 first and again last** (after 20–30 minutes of using the others, no restart):
  if E2 is much slower the second time, memory build-up is part of the problem (the restart check).

  | Book | TOC jump (s) | Page jump to 75% (s) | 10 page turns (s) | Crash? |
  |---|---|---|---|---|
  | E2 (fresh restart) | | | | |
  | E1 | | | | |
  | E3 | | | | |
  | E4 | | | | |
  | E5 | | | | |
  | E2 (again, no restart) | | | | |

- **Reading the results:** E3 fast → bytes; a shorter marker is enough. E3 slow but E4 fast → amount per
  file; step 7 splits files. E5 fast → another reader route (reopens D54). Nothing fast → rethink.

## 9. Parking lot (future ideas, not this project)

Good ideas go here so they're not lost, but they don't expand this project's scope.

- **P1. Bold-start desktop app for Ubuntu, packaged as a snap.** It reuses the `boldstart/`
  engine (D8), which is why that engine is built as a separate library from day one.
- **P2. KOReader**, if Kobo's built-in reader ever proves not to be enough. See D13.
- **P3. Automatic Google Drive sync**, instead of downloading Google Docs as `.docx` by hand.
- **P4. Generated covers** for converted documents (which otherwise show as plain tiles), reusing the
  Spike D screen code.
- **P5. Our own operating system for the Glo**, after this project is finished. First make a full image of the internal microSD card (the backup), then experiment only on a copy. Lighter ways in: an app that runs on Kobo's Linux in place of Nickel, as KOReader and Plato do. The hard part of a full OS: the e-ink display driver and its waveform files, and support for the Glo's i.MX50 chip in current Linux, which needs research.
  **Owner's choice (2026-10-24):** start with the lightest way, our own app in place of Nickel, and explore options there. **Goal: Wi-Fi sync without today's risks.** The risks (contacting Kobo, auto-updates) come from Nickel, not the Wi-Fi hardware, so with Nickel not running, Wi-Fi only talks to the owner's computer.

## 10. Glossary

| Term | Meaning |
|---|---|
| ADR | Architecture Decision Record: a written note of a decision and why it was made |
| Archive (GitHub) | Marking a repository read-only: still public and downloadable, but finished |
| Atomic | Happens completely or not at all, with no half-done state (for example, renaming a file) |
| Dependency | A library your program needs that someone else wrote |
| Interface | An agreed shape that parts of a program follow, so one part can be swapped for another |
| Brick | To leave a device unable to start, "as useful as a brick" |
| Conflict (sync) | When the same file changed in two places and a program must guess which one wins |
| DRM | Digital Rights Management: a lock on a file that controls who can open it |
| EPUB | The standard ebook file format; inside, it's basically a small website in a zip file |
| Feasibility spike | A small throwaway experiment to answer "can this even work?" |
| Hash | A short "fingerprint" computed from a file's contents; change one letter and the hash changes |
| KOReader | Open-source reading app for e-readers |
| Library (code) | Reusable code that other programs build on; it isn't a program by itself |
| Metadata | Information stored *about* a file inside it, such as a book's title and author |
| MoSCoW | Prioritising as Must / Should / Could / Won't |
| Nickel | Kobo's own reading software |
| Parking lot | A list of good ideas deliberately held for later |
| Pipeline | A series of steps where each one's output feeds the next |
| Polling | Checking for something at regular intervals ("is the Kobo there yet?") |
| Push / Pull | Sending files *to* a place / fetching files *from* a place |
| Scope | What a project will and won't do |
| Separation of concerns | Splitting code so each part has one job and doesn't depend on unrelated parts |
| Scenario walkthrough | Pushing a pretend real-life case through a design on paper to find gaps before coding |
| Snap | Ubuntu's app package format, installed with `snap install` |
| Snap confinement | The walls around a snap: it can only reach what it declares (USB drives, network, notifications) |
| Source of truth | The one place whose copy wins if two copies disagree |
| systemd user service | A background program Ubuntu starts and looks after for you, running as you (not as root) |
| Test double | A stand-in used in tests, such as a temporary folder pretending to be the Kobo |
| TOML | A simple settings-file format meant to be read and edited by people |
| Virtual environment (venv) | A private Python installation for one project, so its libraries don't clash with others |

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
- **2026-10-23:** Spike A: bold-start works on the Glo; **30%** preferred. A reader freeze was traced
  to a missing `toc.ncx` with a control experiment (D12). KOReader parked (D13); themes dropped.
- **2026-10-23:** Spike D: custom sleep screen built (`spikes/screens/make_screen.py`) and working (needs
  "Show current read" + "Show book covers full screen" ON). Boot animation format decoded. Tool named
  `kraken` (D16). Planned font picker, auto-sync on plug-in (R14) and the walking-skeleton build order (D17).
- **2026-10-23:** Scenario walkthrough: a Gutenberg EPUB, a PDF newsletter and an AI-written `.docx`.
  Biggest find: without a push record, books deleted on the Kobo would be re-sent (Q8). Decided the `KRAKEN`
  folder (D19), the end state of a snap release and then an archived repo (R15, D20), and the PDF ladder (D21).
  Making `KRAKEN/` an inbox with a `sent/` folder (D22) solved the re-sent-books problem with no extra machinery.
- **2026-10-23:** README polished (it now says the Kobo runs official firmware in Sideloaded Mode, not a
  stripped system). Decided to build the owner's own tool first (D23). Drafted `DESIGN.md`: folders, the
  8-step pipeline, four commands, settings, engine rules, auto-sync via a systemd user service, tests, and
  milestones. The owner approved it with every recommendation (D24–D26): **Phase 3 done**. Added visual
  bold-start examples to the README (Alice, in four styles) and named ADHD there, the owner's choice.
- **2026-10-23 (late):** The Kobo wouldn't power down, so the owner held the light button and slid the
  power switch: a **second factory reset**, back to 2.1.5. Recovered with the firmware saved in `downloads/`
  (checksums checked on the computer and again read back from the Kobo). **New finding: 2.1.5 installs
  firmware straight from its setup screen**, so the offline placeholder user isn't needed. Then
  `SideloadedMode=true` and the sleep screen were restored. Backups are in `backups/2026-10-23-after-second-factory-reset/`
  and `backups/2026-10-23-after-fw-4.38-second/`. **Recovery recipe:** reset → copy firmware → eject → wait →
  Sideloaded Mode → restart → sleep screen + two Energy saving settings → **open a book** (the sleep
  graphic only shows when a book is in progress; see Spike D). Sleep screen confirmed working.
- **2026-10-23 (late):** **Phase 4 done.** Ubuntu leaves out Python's venv tool, so the owner installed
  `python3-venv`. Added `pyproject.toml` (license GPL-3.0-only, matching the README), the `boldstart/` and
  `kraken/` packages, and `kraken/cli.py` with `--help` and `--version`. The venv installs it, the `kraken`
  command runs, and the first test passes. Decisions D27–D30.
- **2026-10-23/24 (night):** **Milestone 1, steps 1–8 built**, each with its own tests and commit (116 tests).
  Design refinements found while building: copies are verified by reading back from the device, not the page
  cache, *before* the rename; unfinished copies end `.kraken.part`; FAT ignores case, so name checks do too;
  the manifest is saved before copying with new files marked pending (a write-ahead log), so a pulled cable
  can't make kraken's fonts look hand-added; deleting is refused outside `fonts/`; a read-only mount stops
  early. Safety tests were checked by breaking the code on purpose (mutation testing). New modules `push.py`
  and `lock.py`. Not yet run against the real Kobo: that's Checkpoint A.
- **2026-10-24:** Font catalogue set up with **Atkinson Hyperlegible** (Regular, Bold, `OFL.txt`); kraken's
  `read_catalogue()` reads it with no problems. Literata not added yet. The owner put Spike C samples in
  `inbox/`: one article as `.md`, `.txt` and `.pdf`; an AI-written `.docx` (made with python-docx) and the
  same text as `.odt` (made with Pandoc); three more text PDFs (a web page printed from a browser, a
  page-layout booklet, a book); two DRM-free EPUBs; and a `.docx` downloaded from Google Docs.
  The Google one is built differently: no `docProps/` folder, no paragraph styles at all, so its section
  titles are plain paragraphs and converters won't see them as headings. It also has 43 Chinese characters,
  which tests what happens when a font (such as Atkinson) has no glyphs for them. Decided not to support
  RTF (D35).
- **2026-10-24:** **Checkpoint A passed** on the real Kobo. `kraken fonts` → `push --dry-run` → `push`
  installed Atkinson; the copies were byte-identical to the catalogue and matched the manifest's hashes. The
  eject worked from kraken, and the desktop notification appeared. The Kobo listed the new font **without a
  restart**, and `.kraken/` didn't appear as a book. Unticking and pushing removed only kraken's two files;
  a hand-added font (`NotoEmoji-Regular.ttf`, a variable font) survived, and it also showed and displayed
  in the Kobo's menu. **Found:** Atkinson with only Regular and Bold made Alice's italic words show as bold:
  the Kobo falls back to the Bold file. Added Atkinson's Italic and Bold Italic (v1.006, from the official
  googlefonts repository, each checked against GitHub's own file hash), pushed all four, and the italics now
  lean. Added a warning for families with no Italic (D36). Not yet checked: bold-start using the real Bold,
  which needs Milestone 2's books.
- **2026-10-24:** **Step 9 built** (`kraken autosync on`/`off`/status and the watcher; D37–D42), tested with a
  pretend clock and a pretend `systemctl`, and checked by breaking six key lines on purpose. **Checkpoint B
  passed:** with auto-sync on, plugging in and tapping Connect pushed, ejected and notified by itself, about a
  second after the Kobo was mounted; plugging in again did it again. **The two risks didn't happen:** the eject
  and the notification both work from the background service. With kraken's lock held (standing in for a long
  `kraken pull`), the watcher stepped aside and left the Kobo connected; a push run by hand then worked. With
  auto-sync off, plugging in did nothing. One fix: the service's journal stayed empty because Python holds
  back printed lines when there's no terminal, so the unit file now sets `PYTHONUNBUFFERED=1`. **Milestone 1
  is finished.**
- **2026-10-24:** **Milestone 2 planned** (D43–D52, every recommendation approved). **Steps 1–3 built**, each
  checked by breaking key lines on purpose. Step 1 (`text.py`): the mutation check found an unreachable branch,
  removed. Step 2 (`page.py`): the tests caught a real bug the real-book round trip had missed: the text after
  each new marker was bolded a second time (so 30% looked heavier). Fixed, with a test that no two markers sit
  side by side; bolding also got twice as fast. Books are parsed with entity expansion and network access off.
  Step 3 (`epub.py`): pages found through the OPF; `mimetype` first and uncompressed; locked books refused
  before anything is written; a failed book leaves no half-written file. *Alice* and the two inbox EPUBs bold
  in about a second each and round-trip (lxml only re-quotes the DOCTYPE line). lxml 6.1 added (D27).
- **2026-10-24:** **Step 4 built** (`kraken/checks.py`). `check_book` refuses, with a reason for `skipped/`: not a
  zip, locked (checked before anything else is read, D46), damaged (every file compared with its CRC
  fingerprint), no readable OPF, or no `toc.ncx` in the zip (found by its type, not its name; D47).
  `check_bolded` is the light check on our own copy: not damaged, `mimetype` first and uncompressed. The three
  real books pass both. Breaking key lines on purpose found one weak test (the "mimetype first" test was
  really caught by the "uncompressed" rule), now fixed. 227 tests pass.
- **2026-10-24:** **Step 5 built** (`kraken/inbox.py`). `scan_inbox` only looks, never moves: books (`.epub`, any
  case), files for a later version (D49), files changed in the last 10 seconds (D50; a date in the future
  doesn't wait forever), and clashes (two books with the same name on the Kobo: the first by name order is
  sent, the other waits). Hidden files, `.part`/`.crdownload` and sub-folders are ignored. While building it, we
  noticed that the Kobo's FAT drive ignores capitals, so `Alice.epub` and `alice.epub` clash too (D53).
  `file_sent` replaces the older original in `sent/`; `file_skipped` writes a `.why.txt` note (D53). Breaking
  key lines on purpose found one check that made no difference, now removed. 249 tests pass.
- **2026-10-24:** **D54:** `.kepub` is dropped from book names (owner's choice). **Step 6 built:** `kraken push`
  now sends books. Fonts are planned first (reading only, so a damaged manifest still stops before anything
  changes), then books are sent, then fonts are synced. Each book: `check_book`, bold in a temporary folder
  (D52), `check_bolded`, safe copy to `kraken/`, then the original goes to `sent/`. A book kraken can't use
  (locked, no `toc.ncx`, a broken page, or a bolded copy that fails its check) goes to `skipped/` with a note,
  and doesn't count as a problem. A failed copy, or an unexpected error, leaves the book in the inbox for next
  time and *is* a problem; the other books still go. Leftover `.kraken.part` files in `kraken/` are removed.
  The summary reads like "Books: 2 sent, 1 skipped (see skipped/), 1 waiting. Fonts: … Safe to unplug.", and the
  terminal names every waiting file and why. `--dry-run` checks each book and says "would send" or "would
  skip", without bolding or creating anything. Breaking key lines on purpose found three gaps in the tests
  (the toc check, the bolded-copy check, and a broken page), now covered. 267 tests pass.
- **2026-10-24:** **Checkpoint C started.** Preview in Calibre's viewer: *Mortuary Customs* shows bold-start, and no
  heading (`<h1>`–`<h6>`) is bolded. Some books write titles as plain paragraphs (Watts: `<p class="h2c1">`); those
  *are* bolded. **Strength re-test:** a throwaway test book (not in the repo) held the same Watts excerpt at 30, 40,
  45, 50 and 60%, made with the real engine, and was put in `kraken-tests/` on the Kobo with kraken's safe copy.
  The owner changed fonts and sizes without a freeze, and liked 30% to 60% depending on font and size. **D55:**
  default 0.45. Open: Q13 (varying strength), Q14 (a GUI). `kraken push --dry-run` on the real Kobo listed both
  test books correctly.
- **2026-10-24:** **Checkpoint C on the Kobo.** Auto-sync sent both books (notification "2 books sent, safe to
  unplug"); titles, 45%, plain headings in Yarrow and italics all good. **Failed on speed:** TOC and page jumps
  take 20–30 s in the bolded books, Yarrow's page turns are slow, and one TOC jump in Yarrow crashed the reader.
  The unbolded *Alice* is fast (after a slow first open, which is normal: the reader counts pages). Measured:
  bolding makes each chapter file about 5× bigger, because every word gains `<b class="kraken-bs">…</b>`.
  Yarrow's files grow from 76 to 391 KB, past the ~260–300 KB that the Adobe engine handles well (Calibre
  splits EPUB files over 260 KB for this reason). Spike E will test a shorter marker and split files.
- **2026-10-24:** **Spike E planned and built.** Measuring both books showed Watts's bolded files are only 174 KB,
  under the ~260 KB limit, yet were also slow, so the spike separates bytes from element count. The owner asked
  about the Kobo's memory: no setting exists for it, and swap would need system changes, so a restart check was
  added instead. `spikes/big-files/make_variants.py` builds E1–E5 (results table in section 8b); every version
  passes `check_bolded`. Waiting for the Kobo test.
- **2026-10-24:** **Spike E books sent.** The first try failed: auto-sync ran a push on plug-in and ejected
  the Kobo (D26) before the books could be copied, even with nothing to send. With auto-sync off, all five
  books went to `kraken-tests/` with kraken's safe copy, and the Kobo was ejected. To think about later:
  auto-sync always ejects, so any manual job on the Kobo means turning it off first.
- **2026-10-24:** The owner worried that plugging in so often would wear out the Kobo's micro-USB socket, and asked about Wi-Fi sync, then about blocking Kobo's servers. **D56:** no Wi-Fi; a data-capable magnetic adapter spares the socket instead. Building our own OS for the Glo parked as P5.
