# Kobo-FOMO

Turning my old Kobo Glo e-reader into a calm, distraction-free reader where everything I read is in
**bold-start lettering**.

## Why

I have Irlen syndrome and ADHD, which make reading hard: my eyes struggle to track the lines and make out
the words, and there's a lot of shifting and merging going on. ADHD in particular has greatly contributed
to my reading and learning difficulties. If you have ADHD and reading is a struggle, bionic-style lettering
is worth knowing about. It's lettering where the first part of each word is in bold. The best-known version
is the Bionic Reading method:

> "Renato Casutt created the Bionic Reading Method, which uses an algorithm to strategically bold the
> first few letters of words (fixation points) to guide the eyes and allow the brain to process words
> faster."
> ([bionic-reading.com](https://bionic-reading.com/br-method/))

The problem: I've been trying since 2016, when I first saw an example of it, to get what I want to read
(e-books, EPUBs, PDFs, documents) into that format easily and affordably, and to read it on an e-reader.
I never found a reliable way I could afford. Maybe I didn't look hard enough. So I'm building one.

## What it looks like

The opening of *Alice's Adventures in Wonderland* (Lewis Carroll, 1865, public domain), in four styles.
Everyone's eyes are different, so try them all: read each one, and notice which feels easiest to follow.

**Plain, for comparison**

> Alice was beginning to get very tired of sitting by her sister on the bank, and of having nothing to do: once or twice she had peeped into the book her sister was reading, but it had no pictures or conversations in it, ‘and what is the use of a book,’ thought Alice ‘without pictures or conversations?’

**Light bold-start (30% of each word): what I use, and kraken's default**

> **Al**ice **w**as **beg**inning **t**o **g**et **ve**ry **ti**red **o**f **sit**ting **b**y **h**er **si**ster **o**n **t**he **ba**nk, **a**nd **o**f **ha**ving **not**hing **t**o **d**o: **on**ce **o**r **tw**ice **s**he **h**ad **pe**eped **in**to **t**he **bo**ok **h**er **si**ster **w**as **rea**ding, **b**ut **i**t **h**ad **n**o **pic**tures **o**r **conv**ersations **i**n **i**t, ‘**a**nd **wh**at **i**s **t**he **u**se **o**f **a** **bo**ok,’ **tho**ught **Al**ice ‘**wit**hout **pic**tures **o**r **conv**ersations?’

**Heavy bold-start (50% of each word)**

> **Ali**ce **wa**s **begin**ning **t**o **ge**t **ve**ry **tir**ed **o**f **sitt**ing **b**y **he**r **sis**ter **o**n **th**e **ba**nk, **an**d **o**f **hav**ing **noth**ing **t**o **d**o: **on**ce **o**r **twi**ce **sh**e **ha**d **pee**ped **in**to **th**e **bo**ok **he**r **sis**ter **wa**s **read**ing, **bu**t **i**t **ha**d **n**o **pict**ures **o**r **convers**ations **i**n **i**t, ‘**an**d **wh**at **i**s **th**e **us**e **o**f **a** **bo**ok,’ **thou**ght **Ali**ce ‘**with**out **pict**ures **o**r **convers**ations?’

**Every other word (50%)**: fewer bold spots, so the eyes jump further each time

> **Ali**ce was **begin**ning to **ge**t very **tir**ed of **sitt**ing by **he**r sister **o**n the **ba**nk, and **o**f having **noth**ing to **d**o: once **o**r twice **sh**e had **pee**ped into **th**e book **he**r sister **wa**s reading, **bu**t it **ha**d no **pict**ures or **convers**ations in **i**t, ‘and **wh**at is **th**e use **o**f a **bo**ok,’ thought **Ali**ce ‘without **pict**ures or **convers**ations?’

On the Kobo's e-ink screen, with a font that has a real bold, the effect is crisper than in a web browser.
In kraken, the strength is one number in the settings file, so you can tune it to your own eyes.

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
