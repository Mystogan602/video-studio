# Video formats

Pick the row, then adjust only what the brief asks for. Canvas and subtitle settings go into `video.json` (or the workspace `defaults.json`).

| Type | Canvas | Subtitles | Length | Footage | Section cards |
|---|---|---|---|---|---|
| **Demo — phone app** | device width × (device height − cropped status bar + band), e.g. 1080 × 2700 | `band` (under the screen, never covers the app) | 3–6 min, clips 20–60 s | `recording` (Android) + `slides` for stills | yes |
| **Demo — web app** | 1920 × 1080 | `overlay` | 2–5 min | `recording` (web) | yes |
| **Explainer / tutorial** | 1920 × 1080 | `overlay` | ~2 min per concept | `slides` (HTML) or `rendered` | chapter cards |
| **Short (vertical)** | 1080 × 1920 | `overlay`, bigger font (72–84), `bottomMargin` ≥ 360 to clear platform UI | 30–60 s, one idea | any | no |
| **Report / walkthrough** | 1920 × 1080 | `overlay` | 2–5 min | `slides` (HTML charts, screenshots) + short recordings | optional |

## Structure per type

### Demo (product, sprint, feature)
1. **Opening card** — greeting, scope in one sentence ("In this sprint I built three things: A, B and C"), the plan ("I'll show them one by one").
2. **One clip per user-visible area** (≤ 6). First line = transition + why ("First, search. Before, you could only filter by distance, so I added…"). Then 2–5 steps: action → visible result. Bug fixes: old symptom → fixed behaviour on screen.
3. **Closing card** — wrap-up, one-sentence outcome for the user, optional one sentence on invisible work, thanks + where to send feedback.
No ticket keys, internal names, endpoints or "who asked for it".

### Explainer / tutorial
1. **Hook** (≤ 5 s): a concrete failure or question with a visible consequence.
2. **Roadmap** (≤ 60 s in): what the viewer will be able to do.
3. **Per concept**: problem in one running example → how it works (built step by step) → real code / artifact → common mistake → when (not) to use → one-sentence recap.
4. **Recap**: answer the opening question with the mechanism; 2–3 short rules.
5. **One call to action** (an exercise, a link) — only one.
Avoid several endings in a row (recap, takeaways, teaser, conclusion…).

### Short
Hook in the first 2 s (on screen and in the narration) → one idea → payoff → end. No greeting, no section cards, no "subscribe" padding. The picture changes at least every 3–4 s.

### Report / walkthrough
Opening card (period, scope) → one clip per area with the number first, then the cause ("Revenue +12 %: two new stores opened") → risks / blockers → next steps only if the audience asked for them → closing card.
