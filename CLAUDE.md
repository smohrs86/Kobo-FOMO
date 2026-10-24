# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

Kobo-FOMO turns an old **Kobo Glo** (N613, 2012) into a distraction-free reader with
**bold-start lettering** (bionic-style reading) as an accessibility accommodation.
**KOReader** is the reading app (it replaces Kobo's own interface), and a Python pipeline
on the computer converts and bolds books, then copies them to the Kobo over USB.

`PLAN.md` is the source of truth for requirements (R#), decisions (D#), phases, risks and
the project log. Read it before proposing work, and update it whenever a decision is made.

**Starting a session:** read section 0 of `PLAN.md` ("Where we left off") first, and continue from
its "Next up" list. **Ending a session:** update section 0 and the project log, then commit and push.

## Repository layout (so far)

- `PLAN.md`: plan, decisions, spike results, project log
- `DESIGN.md`: approved design for the `kraken` tool (folders, pipeline, commands, tests, milestones)
- `spikes/`: throwaway experiments (`boldstart-sample/` = Spike A, `screens/` = Spike D)
- Git-ignored, local only: `backups/` (device files), `downloads/` (firmware, fonts, control books),
  `inbox/` (documents to convert), `personal/` (owner photos and custom screens)
- Tools available: Python 3 + Pillow, Calibre (`ebook-convert`), Pandoc, LibreOffice, `udisksctl`

## How we work

- **Plan twice, code once.** Agree on the plan in writing before writing code. Ask
  clarifying questions when intent is unclear.
- **This is a learning project.** The owner is a computer science student who builds with
  AI assistance. Explain new terms in plain English the first time they come up, explain
  what each piece of code does and why, and gently give the correct term when one is
  used loosely.
- **Clean, readable code** over clever code. Small, tested steps, one feature at a time.
- Record decisions as `D#` entries in `PLAN.md`, with the reason. IDs are never reused
  or renumbered; dropped items are struck through.
- Commit and push meaningful changes without asking, **after** the privacy check below.
  Commit messages explain *why*. If the check finds anything personal, stop and ask.

## Device safety rules

- **Never let the Kobo onto Wi-Fi.** On 2026-10-23 it auto-updated over Wi-Fi, was
  interrupted, and boot-looped. Firmware changes are done manually over USB, by choice.
- **Back up any file on the Kobo before editing it** (to `backups/`, which is git-ignored).
- **Verify downloads with their checksum** before copying them to the device.
- **During a firmware update, a black or striped screen means wait.** Never power off.
- Eject safely (`udisksctl unmount` then `udisksctl power-off`), then the user unplugs.
  The Kobo stays on its "connected" screen until the cable is physically removed.
- If USB misbehaves, suspect the cable first.
- The Kobo reads `.kobo/Kobo/Kobo eReader.conf` **only at startup**: restart it after editing.
- The device runs firmware 4.38.23429 in **Sideloaded Mode** (`SideloadedMode=true`), with no Kobo account.
- The Kobo mounts at `/run/media/$USER/KOBOeReader`; device files live in `.kobo/`.
- Custom sleep screen: one image in `.kobo/screensaver/`, with both "Show current read" and
  "Show book covers full screen" ON (Settings → Energy saving and privacy).

## Legal and ethical rules

- **Never help remove DRM** (for example from library or store books). Library loans are
  out of scope (D2).
- Don't commit Kobo firmware or other third-party copyrighted files.
- Call the feature "bold-start", not "Bionic Reading" (a trademark; see D3).

## Privacy: this repository is PUBLIC

Everything committed here is published. Before any commit, check that no file contains:

- names, emails, usernames, or home-folder paths (use `$HOME`, `$USER`, or relative paths)
- device serial numbers, MAC addresses, or device or user IDs from Kobo databases
- location, contact details, or anything else that could identify the owner
- copies of `.kobo/` files, databases, or logs from the device (they contain IDs)

Personal data belongs in git-ignored folders (`backups/`, `downloads/`, `library/`).
Commits use the owner's GitHub "noreply" email, never a personal address.
The owner has chosen to describe the accessibility purpose (Irlen syndrome and ADHD) publicly.
That is intentional, but don't add any further personal health detail.
