# ListenMD — Format Specification v0.1

> Part of the **LearnSpec** suite
> Status: Draft — September 1, 2026

---

## Core Principle

ListenMD is the **speech-only rendition format** of the LearnSpec suite. A ListenMD script (`.listen.md`) is what a piece of content becomes when it is rendered for ears instead of eyes: an ordered sequence of spoken turns, grouped into optional chapters, each turn attributed to an abstract voice **role**.

A ListenMD script contains nothing a text-to-speech engine cannot read aloud. There are no images, no tables, no code blocks, no lists, no LaTeX, and no markup meant to be looked at rather than heard. This constraint is what makes the format safe to synthesize blindly: whatever a producing pipeline puts in a `.listen.md` file, a renderer can hand straight to a TTS engine, turn by turn, without guessing what to skip.

| Principle | Description |
|---|---|
| **Markdown-first** | A ListenMD script is valid Markdown, readable in any editor: headings, `@role` turn markers, prose paragraphs |
| **Speech-only** | Everything outside frontmatter and blockquote asides is spoken verbatim. No visual content, no deixis to something the listener cannot see |
| **Role-abstract** | Turns name abstract voice roles (`@host`, `@signpost`, `@guest`…), never a provider, a voice id, or a style tag |
| **Provider-agnostic** | Which concrete voice renders a role — provider, voice id, style, speed — is a decision made outside the file, by the pipeline that renders it |
| **Graceful degradation** | A `.listen.md` file renders as a perfectly readable transcript in any standard Markdown reader |

---

## Positioning: A Rendition Format

ListenMD is not an authoring format for instruction — that role belongs to content formats like LearnMD. A ListenMD script is a **derived rendering target**: it is produced by rewriting an existing piece of content (typically a LearnMD lesson, but the source can be any content format) for a listener who cannot see a diagram, a table, or a bullet list.

That derivation is deliberately editorial, not mechanical. Tables get re-linearized into flowing prose, visual references ("the diagram below") get replaced with narration of the mechanism itself, numbers get written the way they are spoken, and roughly the material that carries the core argument gets kept while the rest is dropped. A ListenMD file does not attempt to preserve everything its source contains — it attempts to sound good.

Because of this, ListenMD does not satisfy the suite-wide expectation that "any LearnMD works in every profile it targets" — it is what a lesson becomes *after* being rewritten for one specific profile: listening. A forthcoming amendment to the [LearnSpec Architecture Charter](https://learnspec.org/charter/) formalizes the **rendition format** category this introduces; this specification defines the format itself and leaves the category's cross-suite rules to the charter.

---

## File Structure

A ListenMD file follows the suite's universal structure: an optional YAML frontmatter block, followed by Markdown content.

```
[Optional YAML frontmatter between --- delimiters]
[Markdown content: chapters, turn markers, spoken paragraphs]
```

Following the charter's [Level system](https://learnspec.org/charter/#level-system):

| Level | What it adds |
|---|---|
| **0** | Turn markers and spoken paragraphs, no frontmatter, no chapters. Every `@role` turn is implicitly in one unnamed chapter |
| **1** | YAML frontmatter (`title`, `lang`) |
| **2** | Chapter headings (`## `), optionally anchored (`{#slug}`) into a source document for audio↔text sync |

Each level is a strict superset of the previous one — a Level 0 script is valid at Level 2.

---

## Frontmatter

```yaml
---
title: "El Niño: the ocean that reshapes the world"
lang: en
spec_version: "0.1"
---
```

| Key | Read by the parser | Description |
|---|---|---|
| `title` | Yes | The episode title. `title: "text"` and `title: text` (quotes optional) are both accepted |
| `lang` | Yes | BCP-47 language code (`en`, `fr`, `en-US`…) — the language every spoken turn in the file is written in |

No other key is read. The charter's other [universal frontmatter fields](https://learnspec.org/charter/#universal-frontmatter) (`spec_version`, `author`, `tags`, `created`, `updated`, `license`) may be present for consistency with the rest of the suite, and any other key a producing pipeline finds useful (a source reference, an estimated duration, a rendering profile) may be present too — **all of them are ignored by a conforming parser**. This is intentional: metadata about *how* to render the file (voice bindings, provider, mastering levels) belongs to the pipeline that renders it, never to the file, so that the same script stays renderable by any TTS stack. A file with no frontmatter at all is valid (Level 0); `title` and `lang` are then both empty, and validators SHOULD warn (see [Validation](#validation)).

---

## Chapters

A line starting with `## ` opens a **chapter** — a named group of consecutive turns.

```markdown
## The problem with noise
```

The `{#slug}` anchor form is optional:

```markdown
## The problem with noise {#the-problem-with-noise}
```

| Form | Chapter title | Anchor |
|---|---|---|
| `## The problem with noise` | `The problem with noise` | none |
| `## The problem with noise {#the-problem-with-noise}` | `The problem with noise` | `the-problem-with-noise` |

The anchor, when present, is **stripped from the spoken/displayed title** — it is never read aloud and never shown as part of the chapter name. Its meaning is normative: it is the heading id/slug of the corresponding section in the **source document** this chapter was rewritten from (typically a `##`/`###` heading in a LearnMD lesson). A player that shows the source text alongside the audio uses the anchor to scroll the two in sync as chapters change.

A chapter without an anchor is legitimate and common — an opening teaser, a closing recap, or any chapter that blends several source sections or introduces none, has no single section to point to. Anchors are opt-in per chapter, not all-or-nothing across a file.

A chapter's anchor slug MUST match `[A-Za-z0-9][A-Za-z0-9_-]*` and MUST be copied character-for-character from the source document's own heading id — a producing pipeline must never invent, transliterate, or guess one. A heading whose trailing `{#...}` does not match that shape is not recognized as an anchor at all: the literal text, braces included, stays part of the spoken chapter title (a strong signal something upstream is malformed — see [Validation](#validation)).

A file needs no chapters at all: every turn before the first `## ` heading belongs to an implicit, unnamed chapter (`chapter: null`), same as at Level 0.

---

## Speech Turns

A line consisting of exactly `@` followed by a role name opens a **turn** — the unit of spoken text attributed to one voice.

```markdown
@host
Every bridge you've ever crossed is quietly losing a fight with gravity — and winning anyway.
```

A role name matches `[A-Za-z_][A-Za-z0-9_-]*` and is compared case-insensitively (`@Host` and `@host` are the same role). Everything between one `@role` line and the next state change — another `@role` line, a `## ` chapter heading, or the end of the file — is that turn's **spoken text**: one or more paragraphs of plain prose, separated by a blank line.

A turn with no non-blank text after it produces nothing — an empty or whitespace-only turn is silently dropped, never rendered as a zero-length segment. Text that appears **before** the first `@role` line of the file has no turn to belong to and is silently discarded; a document should always open with a role.

### Roles

The role vocabulary is **open**: any `@word` matching the syntax above is accepted, whatever the word is. Three roles are conventional across the suite's reference producers:

| Role | Carries |
|---|---|
| `@host` | The narration — the voice that carries the knowledge, the argument, the throughline |
| `@signpost` | Short structural capsules — recaps, transitions, "remember this" landmarks — used sparingly, never for the bulk of the content |
| `@guest` | A curious co-host in dialogue-style episodes — asks the questions a listener would ask |

A renderer that receives a role it does not recognize is expected to degrade gracefully (e.g. fall back to a default voice) rather than fail the whole episode — see [Provider-Agnostic Rendering](#provider-agnostic-rendering). This specification does not fix the set of roles a script may use, nor how many roles a script must use: a single-voice trailer and a four-voice panel are both valid ListenMD.

---

## Spoken Text

Everything inside a turn is prose, meant to be read aloud exactly as written. A few rules follow directly from that:

- **No markdown emphasis.** `*italic*` and `**bold**` are forbidden in authored ListenMD — a TTS engine reads the asterisks aloud as words, audibly so ("star Cahiers du cinéma star"). A conforming parser defensively strips well-formed emphasis pairs it encounters anyway (see [Parsing Rules](#parsing-rules)), but a producing pipeline MUST NOT rely on that as a substitute for not emitting emphasis in the first place.
- **No visual reference.** Nothing in a turn should assume the listener can see anything — "the diagram below," "as shown in the table," and similar phrasing have no correct rendering in audio. A rewrite that would need one narrates the underlying mechanism instead.
- **Numbers, units, and dates are written as spoken.** `1.5 °C` is written `one degree and a half`, not left as a symbol a TTS engine may or may not expand correctly.
- **Prosody is punctuation only.** Pauses and emphasis come from `…` and `—`; no provider-specific markup of any kind (SSML tags, style brackets, etc.) belongs in the file.

---

## What Renders as Speech, and What Doesn't

| Line | Spoken? |
|---|---|
| A paragraph inside an open turn | **Yes** — verbatim, after emphasis stripping |
| `@role` | No — it opens a turn, consumed as structure |
| `## Chapter {#anchor}` | No — the anchor is structure; the chapter *title* is metadata, not narration (a renderer decides independently whether to announce it) |
| `# Document title` | No — a single-hash heading is never spoken and never opens a chapter; it is skipped entirely |
| `> a blockquote line` | No — reserved for asides (shownotes, source links, editorial notes) that accompany the episode but are never synthesized |
| Anything else (a stray table row, an image, a list item, a fenced code block…) | **Yes, verbatim** — ListenMD has no fenced-block or list syntax of its own, so any such line found inside an open turn is read as spoken prose exactly as written. Authors and producing pipelines MUST NOT rely on markdown constructs to convey anything other than plain prose inside a turn |

That last row matters: ListenMD deliberately has no in-body directive for sound design, timing, or mixing (ambience beds, jingle cues, transition swells and the like). Anything of that kind lives entirely on the renderer's side, driven by the file's structure (chapter boundaries, turn boundaries) rather than by markup inside it. A script that contains such a directive does not fail — its lines are simply read aloud as prose, which is the format's way of telling you it doesn't belong there.

---

## Provider-Agnostic Rendering

A ListenMD file never names a TTS provider, a concrete voice id, a speaking style, or a speed. That binding — which voice renders `@host`, in what tone, on what provider — is a decision made entirely **outside the file**, by whatever pipeline renders it, and it may change between renders without touching the script at all: the same file can be read by a premium cloned voice today and a browser's built-in speech synthesis tomorrow.

Two direct consequences for anything built on top of this specification:

- A conforming renderer maintains its own role → voice mapping (a role absent from that mapping SHOULD fall back to a default, typically the mapping's `host` entry, rather than fail the render).
- An episode's "style" — documentary narration, a two-voice dialogue, a short marketing trailer, a personal revision digest — shapes *how* a script is written (how many roles, how chapters are used, target length) but is never itself a field of the file. Two producing pipelines can generate very differently styled scripts that are both, equally, valid ListenMD.

---

## Parsing Rules

This section is normative for a conforming parser.

**Frontmatter.** If the file begins with a line `---`, the parser reads up to the next line that is exactly `---` as a YAML block and treats everything after it as the body. A file that does not open on `---` has no frontmatter; the whole file is the body, and `title`/`lang` are both empty. Within a recognized frontmatter block, only `title` and `lang` are extracted (each read from its own line, independent of the rest of the YAML being well-formed); every other key is ignored without error.

**Body — line by line, top to bottom:**

1. A line starting with `>` is skipped entirely: not spoken, does not close a turn, does not open a chapter.
2. A line starting with `## ` closes the current turn (flushing its buffered text as one segment, if any) and opens a new chapter. The text after `## ` is checked for a trailing `{#slug}`; if the slug matches `[A-Za-z0-9][A-Za-z0-9_-]*`, it becomes the chapter's anchor and is removed from the title, otherwise the whole line (braces included) is the title and the anchor is `null`.
3. A line starting with `# ` (and not `## `) is skipped entirely — no turn or chapter is affected.
4. A line matching `@` + a role name + nothing else closes the current turn (flushing it, if non-empty) and opens a new one under the new role, lower-cased.
5. Any other line is appended, trimmed of trailing whitespace only, to the current turn's buffer.

**Flushing a turn** (on step 2, step 4, and once more at end of file): the buffered lines are joined, split into paragraphs on blank lines, each paragraph is trimmed and empty ones are dropped, and the survivors are rejoined with a blank line between them. Markdown emphasis is then stripped (see below). If anything is left, one segment is emitted, carrying: the role, the resulting text, the current chapter title, and the current chapter anchor (`null` if there isn't one, or if no chapter has been opened yet). If nothing is left — or no role was open when the flush happens — nothing is emitted.

**Markdown emphasis stripping (defensive, not authoring guidance).** A parser SHOULD strip well-formed `**bold**` and `*italic*` pairs from spoken text before it is rendered, narrowly enough to avoid mangling real prose:

- The content between the markers must start and end on a non-space character (rules out ` * ` used as a bare multiplication sign).
- The content must contain no newline and be at most 80 characters long, so that two unrelated asterisks far apart in the same paragraph are never mistaken for a pair and swallow everything between them.
- A lone or unmatched asterisk is left exactly as written.

This is a safety net for content that violates the no-emphasis rule above, not a licence to author with emphasis — a script that relies on it to render correctly SHOULD be flagged by a validator.

---

## Graceful Degradation

| What the file contains | What a standard Markdown reader shows |
|---|---|
| YAML frontmatter | Hidden by most renderers, or shown as a raw metadata block; never breaks the render |
| `## Chapter {#slug}` | A level-2 heading. Most readers show `{#slug}` as literal trailing text; a few (kramdown-style engines) turn it into a heading id and hide it |
| `# Document title` | A level-1 heading |
| `@host` turn marker | A plain paragraph reading `@host` |
| A spoken paragraph | Ordinary prose |
| `> a shownote` | An ordinary blockquote |
| An unparseable or empty file | An empty (or near-empty) document — never an error, never broken markup |

The worst case is always a readable transcript — never a broken render, never hidden content. A `.listen.md` file needs no LearnSpec-aware tool to be read; the tooling only adds narration on top.

---

## What ListenMD Is Not

- **Not an authoring format.** Nobody writes a lesson's actual pedagogy in ListenMD; it is produced *from* a content format, never the other way around.
- **Not a sound-design language.** There is no in-body directive for jingles, ambience beds, transition swells, gaps, or mastering levels. All of that is the renderer's responsibility, driven by the file's structure, never by markup inside it.
- **Not a voice-binding format.** Which provider, which voice id, which style or speed renders a role is configuration that lives with the pipeline rendering the file, never in the file.
- **Not visual in any way.** No images, no tables, no lists, no code blocks, no LaTeX — a ListenMD file cannot express anything a listener would need to see.
- **Not a mechanical filter of its source.** A ListenMD script is an editorial rewrite (selection, re-linearization, translation), not a strip-the-markup pass over a content file — nothing guarantees a lossless mapping back to the source beyond the optional chapter anchors.

---

## Validation

Two modes, mirroring the rest of the suite:

**Lenient (default)** — blocking issues only:
- The file produces zero segments (no spoken text survives parsing) — nothing to render or synthesize.

**Warnings** (promoted to errors in strict mode):
- `lang` absent from frontmatter (charter universal rule).
- `title` absent (no frontmatter `title`, per charter universal rule).
- A chapter heading whose trailing `{#...}` does not match a valid anchor shape — it is read as literal title text, almost never the intent.
- Text found before the first `@role` line of the file — silently discarded by the parser, almost always lost content rather than an intentional omission.
- Markdown emphasis (`*`/`**`) present anywhere in a turn's raw source, even though a conforming parser strips well-formed pairs before rendering.
- A line inside an open turn that resembles a directive, a list item, a table row, or a fenced code block — spoken verbatim as prose, almost never the intent.
- More than one role used for the great majority of a script's text with no `@signpost`/structural role at all — not an error, but usually means a documentary-style script forgot its landmark capsules.

With the source document available, validators SHOULD additionally check that every chapter anchor exists among that document's own heading ids.

---

## Version

| Version | Date | Changes |
|---|---|---|
| 0.1 | 2026-09-01 | Initial draft: frontmatter (`title`, `lang`), chapters with optional `{#anchor}`, open-vocabulary `@role` speech turns, spoken-paragraph rules, defensive emphasis stripping, provider-agnostic rendering principle, degradation and validation rules |
