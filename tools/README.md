# listen_compile.py

A reference compiler for [ListenMD](../SPEC.md) (`.listen.md`): parses a
speech script and synthesizes it to a WAV audio file with a pluggable TTS
backend.

This is a **companion tool**, not the spec. It exists to make ListenMD
usable standalone, without any platform. The format itself is
defined by `SPEC.md` at the repo root — read that first if you're writing
`.listen.md` files by hand or implementing your own compiler/parser.

## Status

Single-file, dependency-free reference implementation. It is intentionally
small: parse the grammar correctly, synthesize with one real TTS backend,
mux to WAV. It is not a mastering pipeline — no loudness normalization, no
ambience/jingle cues, no MP3 export.

## Requirements

- Python 3.11+
- No external dependencies. HTTP calls use the stdlib `urllib.request`,
  audio muxing uses the stdlib `wave` module. Nothing to `pip install`;
  copy `listen_compile.py` anywhere and run it.

## Usage

```bash
# Parse only — no network calls, prints the plan.
python listen_compile.py episode.listen.md --dry-run

# Synthesize to WAV with default voices (host=Kore, signpost=Charon).
export GEMINI_API_KEY=...
python listen_compile.py episode.listen.md -o episode.wav

# Override voices per role (repeatable), and also write chapter marks.
python listen_compile.py episode.listen.md -o episode.wav \
    --voice host=Kore --voice signpost=Charon --voice guest=Puck \
    --chapters episode.chapters.json
```

Full flag list: `python listen_compile.py --help`.

| Flag | Default | Meaning |
|---|---|---|
| `-o, --output` | — | output `.wav` path (required unless `--dry-run`) |
| `--dry-run` | off | parse and print the plan, no network calls |
| `--voice role=voice` | `host=Kore`, `signpost=Charon` | repeatable; binds an abstract role to a Gemini voice name |
| `--style role=text` | none | optional spoken-delivery instruction prepended to a role's turns |
| `--chapters PATH` | — | also write chapter marks as JSON |
| `--turn-gap-ms` | 700 | silence inserted between two turns in the same chapter |
| `--chapter-gap-ms` | 1300 | silence inserted when the chapter changes |
| `--max-chars` | 2800 | a turn longer than this is split across multiple TTS calls (paragraph boundaries, no gap between the parts) |
| `--model` | `gemini-2.5-flash-preview-tts` | Gemini TTS model |
| `--temperature` | 0.7 | Gemini TTS sampling temperature |
| `--api-key` | `$GEMINI_API_KEY` | override the env var |

## Env vars

- `GEMINI_API_KEY` — required for real synthesis (an [AI Studio](https://aistudio.google.com/) key). Not needed for `--dry-run`.

## TTS provider

Only **Gemini TTS** (`generateContent` with `responseModalities: ["AUDIO"]`)
is implemented. The provider interface (`TTSProvider` in
`listen_compile.py`) is a two-method shape — `sample_rate` and
`synthesize(role, voice, text) -> bytes` (raw s16le mono PCM) — so adding a
backend (ElevenLabs, a local model, the browser's own speech synthesis) is
a matter of implementing that interface, not restructuring the tool.

An ElevenLabs backend was deliberately left out for this first cut: it
returns MP3, not PCM, and decoding MP3 without either shelling out to
`ffmpeg` or pulling in a native codec dependency contradicts this tool's
"stdlib only, single file" goal. Gemini's TTS endpoint returns raw PCM
directly, which is what makes zero-dependency WAV output possible here.

Voices are bound per abstract **role**, not hardcoded: the ListenMD body
only ever says `@host`, `@signpost`, `@whatever-role-the-script-uses` — the
role vocabulary is open. `--voice role=name` maps a role to a real Gemini
voice; an unmapped role falls back to the `host` voice, then to whichever
voice was mapped first, matching the source pipeline's own fallback so an
unusual role degrades instead of failing the run outright.

## Output

- **WAV only.** MP3 is out of scope: producing it without `ffmpeg` or a
  native encoder library (e.g. `lameenc`) isn't practical in pure stdlib
  Python, and pulling in either contradicts the "vendor this one file"
  goal. If you need MP3, pipe the WAV through `ffmpeg` yourself.
- Audio is mono, 16-bit PCM, at whatever sample rate the provider returns
  (Gemini TTS: 24 kHz, fixed by the API).
- Chapter marks (title, optional `{#anchor}`, start offset in ms) are
  printed at the end of a real run, and written as JSON with
  `--chapters PATH`:
  ```json
  [
    {"title": "Intro", "anchor": "intro-slug", "start_ms": 0},
    {"title": "Deep dive", "anchor": null, "start_ms": 43200}
  ]
  ```
  `--dry-run` cannot report offsets — no synthesis happened, so there is no
  timeline yet — it only lists chapter titles as part of the plan.

## Dry-run example

Given a ListenMD source with 6 chapters and 26 turns across two roles:

```
title:   El Niño : l'océan qui dérègle le monde
lang:    fr
turns:   26
chars:   9167
chapters: 6
  - Ouverture
  - La machine Pacifique
  - Le basculement
  - L'onde de choc planétaire
  - La fin de l'épisode
  - Récapitulatif

roles:
  @host         turns=23   chars=7915   voice=Kore
  @signpost     turns=3    chars=1252   voice=Charon

planned TTS calls: 26 (max_chars=2800 per call)

(dry run — no network calls, no audio, no timing)
```

## Grammar notes

The parser is a direct, faithful port of the authoritative ListenMD parser
— not the earlier internal R&D
prototype, which additionally understood ```` ```audio ```` fences for sound
cues (ambience beds, jingles). Those are a pre-publication extension, not
part of the public grammar this tool targets. Concretely:

- YAML frontmatter: only `title`/`lang` are read; every other field is
  valid ListenMD but ignored by this compiler.
- `## Chapter Title {#anchor}` opens a chapter; the `{#anchor}` suffix is
  optional and stripped from the spoken/displayed title.
- `# ` (single hash) lines and `> ` blockquote lines are never spoken.
- `@role` on its own line opens a turn; role matching is case-insensitive
  (`@Host` and `@host` are the same role) and the vocabulary is open —
  any identifier works, there is no fixed role list.
- Everything else inside a turn — including a bare `### ` sub-heading or a
  fenced code block, since the format has no such constructs — is read as
  ordinary spoken prose, exactly like the production parser. **A ListenMD
  body should therefore be plain prose only**: if a source still carries
  ` ```audio ` cue fences from the older R&D dialect, their content will be
  read aloud as if it were part of the adjacent turn, not skipped. This was
  observed directly: running this tool against the original R&D sample
  episode (which predates the public spec and still has cue fences) parses
  3 fenced cue blocks into the surrounding turn's text, inflating that
  turn's character count and turn total. A cleaned copy with the fences
  stripped parses to the expected 26 turns / 9167 chars. If you're
  targeting the public ListenMD grammar, this never comes up — just don't
  put fenced blocks in the body.

## Limitations

- WAV only (see above).
- One TTS provider (Gemini).
- No mastering: no loudness normalization, no per-segment level matching,
  no crossfades — just fixed silence gaps between turns/chapters.
- No sound cues (ambience, jingles, sound effects) — out of scope for the
  public ListenMD grammar this tool targets.
- Long turns are split on `--max-chars` for the API's sake but always
  concatenated with **no** gap between the parts — they're one utterance.

This is a reference companion, not the normative spec. When in doubt about
what a `.listen.md` file *should* mean, `SPEC.md` wins; this tool is one
possible (and intentionally minimal) implementation of it.
