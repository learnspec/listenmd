# ListenMD examples

Complete, worked examples of ListenMD scripts, ready to copy.

## `el-nino.listen.md` — a full documentary-style episode

A real ~9-minute episode script (French), adapted from the format's original R&D sample. Two voices — `@host` carrying the narration, `@signpost` dropping in for two "repère" (landmark) capsules the listener is meant to remember — across six chapters, none of them anchored to a source document. It demonstrates:

- the minimal, provider-agnostic frontmatter (`title`, `lang`, `spec_version` — nothing about voices, mastering, or timing, all of which lives outside the file);
- a long-form documentary shape: a short cold open, several content chapters, a `@signpost` recap, and a sign-off;
- the `> [!shownote]` blockquote convention for an aside (source link, chapter list) that accompanies the episode without ever being spoken.

## `dialogue-excerpt.listen.md` — a two-voice conversation with chapter anchors

A short (English) excerpt on how noise-cancelling headphones work: `@host` explains, `@guest` asks the questions a curious listener would ask. Two chapters demonstrate both anchor forms side by side:

- `## The problem with noise {#the-problem-with-noise}` — anchored, as if rewritten from a section of that exact id in a source LearnMD lesson;
- `## Fighting sound with sound` — unanchored, a legitimate chapter with nothing to point back to.

## `trailer.listen.md` — a single-voice teaser

A short (English) trailer: one role (`@host`), four turns, **no chapters at all** — a trailer is listened to start to finish, never navigated. Demonstrates the Level 0/1 shape: frontmatter present, but the body is nothing more than a sequence of turns.

## What makes a good ListenMD source

Anything that would make a listener stop and ask "wait, what am I supposed to be looking at?" needs rewriting before it becomes ListenMD — a table, a diagram callout, a bullet list read as a flat enumeration. The format rewards material that already argues in a straight line: a mechanism explained step by step, a question-and-answer exchange, a handful of concrete promises for a trailer. A page that leans on its layout to make its point needs an editorial pass, not a filter, before it can be spoken.
