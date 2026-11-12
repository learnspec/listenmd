# ListenMD

> **Status:** Draft (v0.1) — not yet stable. Part of the [LearnSpec](https://github.com/learnspec) suite.

**ListenMD** is an open, Markdown-based, **speech-only** format for audio episode scripts — lesson episodes, revision digests, trailers. A `.listen.md` file is an ordered sequence of spoken turns, each attributed to an abstract voice role (`@host`, `@signpost`, `@guest`…), grouped into optional chapters.

ListenMD is the suite's first **rendition format**: not an authoring format for instruction, but a rendering target derived from an existing content format — typically a [LearnMD](https://github.com/learnspec/learnmd) lesson, rewritten for a listener who cannot see a diagram, a table, or a list. The file never names a provider, a voice, or a style — that binding lives entirely in whatever pipeline renders it, so the same script stays playable on any TTS stack. Every failure mode degrades to a readable transcript in any standard Markdown reader.

## Quick example

```markdown
---
title: "Why the sky is blue"
lang: en
---

## Scattering the light

@host
Look up on a clear day and you'll see one thing: blue — not violet, though violet scatters even more.

@guest
Wait, so why isn't the sky violet, then?

@host
Because our eyes are far more sensitive to blue, and part of the violet gets absorbed high in the atmosphere before it ever reaches you.
```

## Specification

See [SPEC.md](./SPEC.md) for the full format specification. Worked examples live in [examples/](./examples/). The shared design principles, universal frontmatter fields, and cross-format directives are defined in the [LearnSpec Architecture Charter](https://learnspec.org/charter/).

## Rendering

A `.listen.md` file is a script, not audio: turning it into a listenable episode requires a TTS pipeline that resolves each role to a concrete voice, synthesizes each turn, and assembles the result (silences, transitions, mastering — all pipeline-side, never in the file). A companion compiler lives in [`tools/`](./tools/README.md).

## Related formats

| Format | Repo |
|---|---|
| LearnMD: instructional content | [learnspec/learnmd](https://github.com/learnspec/learnmd) |
| QuizMD: assessments | [learnspec/quizmd](https://github.com/learnspec/quizmd) |
| FlashMD: flashcards | [learnspec/flashmd](https://github.com/learnspec/flashmd) |
| NuggetMD: micro-learning | [learnspec/nuggetmd](https://github.com/learnspec/nuggetmd) |
| ExerciseMD: exercises with solutions | [learnspec/exercisemd](https://github.com/learnspec/exercisemd) |
| TrackMD: learning paths | [learnspec/trackmd](https://github.com/learnspec/trackmd) |
| CurriculumMD: reference frameworks | [learnspec/curriculummd](https://github.com/learnspec/curriculummd) |
| MediaMD: media catalogue | [learnspec/mediamd](https://github.com/learnspec/mediamd) |
| DiagramMD: diagram syntax | [learnspec/diagrammd](https://github.com/learnspec/diagrammd) |
| AnimMD: step-reveal animations | [learnspec/animmd](https://github.com/learnspec/animmd) |
| GlossaryMD: glossaries | [learnspec/glossarymd](https://github.com/learnspec/glossarymd) |
| BadgeMD: micro-credentials | [learnspec/badgemd](https://github.com/learnspec/badgemd) |
| CertMD: macro-credentials | [learnspec/certmd](https://github.com/learnspec/certmd) |

## Maintainers

This repository is part of the [LearnSpec](https://learnspec.org) suite, initiated and maintained by [memoneo](https://memoneo.app). Issues and pull requests are welcome.

## License

[MIT](./LICENSE)
