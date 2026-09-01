# Changelog

All notable changes to the ListenMD specification are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/).

## [0.1] — 2026-09-01

### Added
- Initial draft: YAML frontmatter (`title`, `lang`, both read; every other key ignored); `## Chapter {#anchor}` headings opening optional chapters, whose anchor ties a chapter to a heading slug in the source document for audio↔text sync; open-vocabulary `@role` speech-turn markers, with `host`/`signpost`/`guest` as the conventional set.
- Spoken-text rules: plain prose only, no markdown emphasis, no visual reference, numbers written as spoken, prosody through punctuation alone.
- Normative parsing rules (frontmatter extraction, chapter/turn state machine, defensive markdown-emphasis stripping), a graceful-degradation table, and lenient/strict validation guidance.
- Positioning as the suite's first **rendition format**: a speech-only rendering target derived from an existing content format (typically LearnMD), rather than an authoring format in its own right.
- The provider-agnostic rendering principle: voice/provider/style binding lives entirely outside the file.
