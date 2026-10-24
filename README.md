# Kobo-FOMO

Turning my old Kobo Glo e-reader into a calm, distraction-free reader where everything I read is in
**bold-start lettering**.

## Why

I have Irlen syndrome and ADHD which makes reading hard: my eyes struggle to track the lines and make out the
words, and there's a lot of shifting and merging going on. What helps me is bionic-style lettering,
where the first part of each word is in bold. The best-known version is the Bionic Reading method:

> "Renato Casutt created the Bionic Reading Method, which uses an algorithm to strategically bold the
> first few letters of words (fixation points) to guide the eyes and allow the brain to process words
> faster."
> ([bionic-reading.com](https://bionic-reading.com/br-method/))

The problem: I've been trying since 2016, when I first saw an example of it, to get what I want to read
(e-books, EPUBs, PDFs, documents) into that format easily and affordably, and to read it on an e-reader.
I never found a reliable way I could afford. Maybe I didn't look hard enough. So I'm building one.

## What I did to the Kobo

Nothing drastic. No hacks, no custom firmware, nothing stripped out.

- Installed Kobo's own official firmware (4.38, the Glo's newest) by hand over USB.
- Turned on **Sideloaded Mode**, which hides the Kobo store and skips the Kobo account, and switched off
  the extras I don't need, like games.
- Keep it **off Wi-Fi**. (It once auto-updated over Wi-Fi, got interrupted, and got stuck restarting.
  Lesson learned.)
- Added my own sleep screen picture.

## The tool: kraken

kraken is a small program on my Ubuntu computer. (The name comes from *kraken*, Kobo's own internal
codename for the Glo.)

- I move what I want to read into a `KRAKEN` folder: EPUB books, Word `.docx` (including Google Docs
  downloaded as `.docx`), LibreOffice `.odt`, PDFs with real text in them, `.txt` and Markdown.
- When I plug in the Kobo, kraken converts each file to an e-book, adds bold-start lettering at the
  strength I choose, copies it over, and ejects the Kobo safely. Sent files move to `KRAKEN/sent/`.
- It never deletes books from the Kobo. I do that myself on the reader.
- I can pull a document back to the computer with the bold-start removed.
- I pick fonts with `kraken fonts`, and they sync to the reader.

No Wi-Fi, no store, no account, no subscription fees, no bloat, no overreach, and no locks on my own
library.

**What it won't do:** library loans (Libby and the like) are locked with DRM, so kraken leaves them alone.
Scanned PDFs (pictures of pages rather than text) aren't supported either.

## Status

Work in progress.

- ✅ Kobo set up: Sideloaded Mode, no Kobo account, Wi-Fi off
- ✅ Bold-start tested on the Glo's screen (30% strength suits me best)
- ✅ Custom sleep screen
- ⏳ kraken: being designed, then built one feature at a time

The full plan, decisions and project log are in [PLAN.md](PLAN.md). Once kraken works for me, I'd like
to share it so other Kobo owners can use it too.

## A note on names

"Bionic Reading" is a trademark of its creator's company, and this project isn't connected to them.
That's why I call my version **bold-start**.

## Credits

Vibe coded with [Claude Code](https://claude.com/claude-code) in the terminal. Assistive lettering for
people with Irlen syndrome, ADHD, or anyone else it helps. Thank you.

Licensed under GPL-3.0 (see [LICENSE](LICENSE)).
