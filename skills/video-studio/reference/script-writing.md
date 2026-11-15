# Writing narration

## One step = one line on screen

- One idea per step, at most 2 sentences, ≤ ~22–25 words per sentence. The step is also the unit of timing: the screen action for a step happens while that line is spoken.
- Spoken, not written: short words, active voice, no parentheses, no lists read aloud.
- Vary openings; do not start every line with the same word ("I…", "Em…", "Then…").
- Describe what the viewer sees, not the implementation (no endpoints, caches, component names) unless the audience is technical and asked for it.
- Never apologise or announce ("this video is a bit long", "today we will…"); promise outcomes ("you'll be able to…").
- No dashes in `text`: the voice turns them into odd pauses. Use a comma or a new sentence.

## Cut these AI tells

A script written by a model sounds scripted when it is read aloud. Rewrite any line that does one of these:

| Tell | Vietnamese example | English example | Say instead |
|---|---|---|---|
| "Not X but Y" for weight | "không chỉ… mà còn…", "đây không phải A, mà là B" | "it's not just X, it's Y" | the plain claim |
| Build-up before the point | "Và đây là điều thú vị…", "Thật ra thì…" | "Here's the thing…", "Honestly?" | the point itself |
| Dramatic one-line closer | "Đơn giản vậy thôi.", "Và thế là xong." | "Simple as that." | end on the last real fact |
| Forced list of three | "nhanh, gọn, tiện" | "fast, simple and powerful" | the one or two that are true and visible |
| Inflated or sales words | "trải nghiệm tuyệt vời", "đột phá", "hành trình", "mượt mà", "hoàn hảo" | "seamless", "game-changing", "journey", "stunning", "delve" | what changed, in numbers or on screen |
| "Serves as" instead of "is / has" | "đóng vai trò là", "mang đến" | "serves as", "boasts", "features" | "là", "có" / "is", "has" |
| Chat leftovers | "Hy vọng video hữu ích!", "Câu hỏi hay!" | "I hope this helps!" | nothing, or the closing from `formats.md` |

## Self-check before Gate 1

1. Reread every line against the tells above and rewrite the ones that match.
2. Every number, name, date and UI label still matches the facts from step 2 and what is on screen; no rewrite dropped or changed one.
3. `subtitle` says the same thing as `text`, and Vietnamese diacritics are correct.

## `text` vs `subtitle`

`text` is read by the voice, `subtitle` is read by the viewer:

| Situation | `text` | `subtitle` |
|---|---|---|
| Numbers | "one to twenty kilometres" | "1 to 20 km" |
| Percentages, symbols | "twelve percent" | "12%" |
| UI labels | Save | “Save” |
| Abbreviations the voice misreads | spell them out | keep them |
| Long line | — | a shorter paraphrase that fits 2 lines |

Keep both saying the same thing; the subtitle may be shorter, never different.

Opening and closing: at most 4 lines each; structure per type in `formats.md`.

## Persona and address

The workspace `profile.md` decides who speaks and how viewers are addressed (first person "I/em", "you/mọi người", a character…). Without a profile: first person singular, neutral and friendly, no slang.

## Language notes

**Vietnamese**
- Numbers in words in `text` ("bốn mươi chín", "một đến hai mươi ki lô mét"); digits and units in `subtitle`.
- English product words are fine inline when the voice reads them well; listen in Gate 2.
- Common pronoun sets: speaker "em" + viewers "mọi người" (team demo); "mình" + "bạn" (casual public). Pick one and never mix.

**English**
- Contractions sound natural ("I've", "you'll").
- Read years and versions explicitly when ambiguous ("version two point one").
