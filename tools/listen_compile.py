#!/usr/bin/env python3
"""listen_compile.py — reference compiler for ListenMD (`.listen.md`).

ListenMD is a speech-only Markdown dialect for audio episode scripts:
YAML frontmatter (title/lang), ``## Chapter {#anchor}`` chapters, ``@role``
speaker turns, and plain prose in between. It is provider-agnostic by
design — the body never names a TTS vendor or voice, only abstract roles
(``@host``, ``@signpost``, ...) that a *rendering profile* (here, CLI flags)
binds to real voices.

This tool does two things:

1. **Parse** a ``.listen.md`` source into an ordered list of speaker turns
   (``parse_listenmd``). ``--dry-run`` stops here and prints the plan —
   no network calls.
2. **Synthesize** each turn with a pluggable TTS backend (only Gemini is
   implemented below) and mux the results into a WAV file, with silence
   gaps between turns/chapters and a chapter-offset report.

Design notes
------------
- Stdlib only. No third-party dependencies: HTTP via ``urllib.request``,
  audio muxing via the stdlib ``wave`` module. This keeps the script
  trivially vendorable — copy the file, no ``pip install``.
- WAV, not MP3: encoding MP3 without a native codec library (e.g.
  ``lameenc``) or shelling out to ``ffmpeg`` isn't practical in pure
  stdlib Python, and this tool deliberately avoids both. See the README
  for the tradeoff.
- The parser is a faithful, provider-agnostic port of the authoritative
  grammar of the ListenMD specification (SPEC.md)
  — not the earlier R&D prototype, which additionally understood
  ```audio fences for sound cues/jingles. Those are a pre-publication
  extension, not part of the public ListenMD grammar this tool targets:
  a ListenMD body is plain prose, so a fenced block here is simply read
  aloud like any other text (matching the production parser's behavior).

Usage
-----
    python listen_compile.py episode.listen.md -o episode.wav
    python listen_compile.py episode.listen.md --dry-run
    python listen_compile.py episode.listen.md -o out.wav \\
        --voice host=Kore --voice signpost=Charon --chapters out.json

Env:
    GEMINI_API_KEY   API key for Google AI Studio (Gemini TTS backend).
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
import urllib.error
import urllib.request
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

# ── Grammar (see SPEC.md, "Parsing Rules") ──────────────────────────

# ``## Chapter Title {#anchor-slug}`` — the anchor is optional and stripped
# from the spoken/displayed chapter title. Kept byte-for-byte identical to
# the production regex so a chapter written against that grammar parses
# the same way here.
_CHAPTER_ANCHOR_RE = re.compile(r"^(.*?)\s*\{#([A-Za-z0-9][\w-]*)\}$")

# Markdown emphasis (``**bold**`` / ``*italic*``) is stripped before a turn
# reaches TTS: a speech engine reads the asterisks aloud verbatim. Deliberately
# narrow (content must start/end on a non-space char, capped at 80 chars) so
# a bare multiplication sign (`` * ``) or two unrelated asterisks far apart
# in the same paragraph aren't mistaken for a matched pair.
_MD_EMPHASIS_RE = re.compile(r"\*\*(\S(?:[^*\n]{0,78}\S)?)\*\*|\*(\S(?:[^*\n]{0,78}\S)?)\*")

# ``@role`` opens a speaker turn. The role vocabulary is open (any
# identifier-like token — ``host``, ``signpost``, ``guest-2``, ...) and is
# lowercased, so ``@Host`` and ``@host`` bind to the same voice.
_ROLE_RE = re.compile(r"^@([A-Za-z_][\w-]*)\s*$")

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
_FM_TITLE_RE = re.compile(r'^title:\s*"?(.+?)"?\s*$', re.M)
_FM_LANG_RE = re.compile(r"^lang:\s*(\S+)\s*$", re.M)


def strip_markdown_emphasis(text: str) -> str:
    """Remove ``**bold**``/``*italic*`` markers, keeping the inner text."""
    return _MD_EMPHASIS_RE.sub(lambda m: m.group(1) or m.group(2), text)


@dataclass
class Turn:
    """One speaker turn: a contiguous block of text read by a single role."""

    role: str
    text: str
    chapter: str | None
    chapter_anchor: str | None = None


@dataclass
class Document:
    """A parsed ListenMD source."""

    title: str
    lang: str
    turns: list[Turn] = field(default_factory=list)

    @property
    def total_chars(self) -> int:
        return sum(len(t.text) for t in self.turns)

    @property
    def roles(self) -> list[str]:
        """Roles in first-seen order (open vocabulary, no fixed set)."""
        seen: list[str] = []
        for t in self.turns:
            if t.role not in seen:
                seen.append(t.role)
        return seen

    @property
    def chapters(self) -> list[str]:
        """Chapter titles in first-seen order (``None``-chapter turns excluded)."""
        seen: list[str] = []
        for t in self.turns:
            if t.chapter and t.chapter not in seen:
                seen.append(t.chapter)
        return seen


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split off the YAML frontmatter and return ``({"title": ..., "lang": ...}, body)``.

    Only ``title``/``lang`` are read here — the same subset the production
    parser reads. Everything else a source may carry in its frontmatter
    (``description``, ``voices:``, ``series``, ...) is valid ListenMD but is
    metadata for humans/other tooling, not for this compiler. A source with
    no frontmatter at all is accepted (empty title/lang, whole text is body).
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {"title": "", "lang": ""}, text
    fm_src, body = m.group(1), text[m.end():]
    tm = _FM_TITLE_RE.search(fm_src)
    lm = _FM_LANG_RE.search(fm_src)
    return {"title": tm.group(1) if tm else "", "lang": lm.group(1) if lm else ""}, body


def parse_listenmd(text: str) -> Document:
    """Parse a ListenMD source into ordered speaker turns.

    Grammar (v0.1, per SPEC.md "Parsing Rules"):
    - YAML frontmatter: only ``title``/``lang`` are read.
    - ``## Chapter Title {#anchor}`` opens a chapter; the ``{#anchor}``
      suffix is optional and stripped from the title.
    - ``# `` (a single hash) lines are titles/comments, never spoken.
    - ``> ...`` blockquote lines (shownotes) are never spoken.
    - ``@role`` on its own line opens a turn for that role; everything
      until the next ``@role``/``## ``/EOF is that turn's spoken text.
    - Blank lines inside a turn are paragraph breaks; consecutive blank
      lines collapse (multiple ``\\n\\n`` do not produce empty paragraphs).
    - Everything else (including a bare ``### `` sub-heading or a fenced
      code block) is treated as ordinary spoken prose, exactly like the
      production parser — ListenMD has no markup beyond the above, so
      nothing else is expected to appear inside a turn.
    """
    fm, body = parse_frontmatter(text)
    doc = Document(title=fm["title"], lang=fm["lang"])

    chapter: str | None = None
    chapter_anchor: str | None = None
    role: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf
        if role and buf:
            spoken = "\n\n".join(p.strip() for p in "\n".join(buf).split("\n\n") if p.strip())
            spoken = strip_markdown_emphasis(spoken)
            if spoken:
                doc.turns.append(Turn(role=role, text=spoken, chapter=chapter, chapter_anchor=chapter_anchor))
        buf = []

    for raw in body.splitlines():
        line = raw.rstrip()
        if line.startswith(">"):
            continue
        if line.startswith("## "):
            flush()
            head = line[3:].strip()
            anchored = _CHAPTER_ANCHOR_RE.match(head)
            chapter = anchored.group(1).strip() if anchored else head
            chapter_anchor = anchored.group(2) if anchored else None
            continue
        if line.startswith("# "):
            continue
        turn_m = _ROLE_RE.match(line)
        if turn_m:
            flush()
            role = turn_m.group(1).lower()
            continue
        buf.append(line)
    flush()
    return doc


def split_long_turn(text: str, max_chars: int) -> list[str]:
    """Split an over-long turn on paragraph boundaries.

    Most TTS APIs reject or degrade on very long single requests. Splits
    are made between paragraphs where possible; a single pathological
    paragraph longer than ``max_chars`` is hard-split as a last resort so
    it can never fail the whole run. Chunks from the same turn are
    concatenated with no gap between them at assembly time (they are one
    continuous utterance, just split for the API's sake).
    """
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    current = ""
    for para in text.split("\n\n"):
        while len(para) > max_chars:
            chunks.append(para[:max_chars])
            para = para[max_chars:]
        if current and len(current) + 2 + len(para) > max_chars:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


# ── TTS provider interface ──────────────────────────────────────────────────


class TTSError(RuntimeError):
    """A TTS backend failed in a way worth surfacing to the caller."""


class TTSProvider(Protocol):
    """Minimal interface a TTS backend must implement.

    ``synthesize`` returns raw PCM audio (signed 16-bit little-endian,
    mono) at ``sample_rate`` Hz — the common currency this tool mixes
    everything in before writing the final WAV. A new backend only needs
    to satisfy this shape; nothing else in the compiler is provider-aware.
    """

    sample_rate: int

    def synthesize(self, *, role: str, voice: str, text: str) -> bytes: ...


DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-preview-tts"
DEFAULT_GEMINI_SAMPLE_RATE = 24_000  # fixed by the Gemini TTS endpoint (s16le mono)


class GeminiTTSProvider:
    """Google AI Studio (Gemini) TTS backend.

    Minimal Gemini TTS client:
    same request shape (``generateContent`` with ``responseModalities:
    ["AUDIO"]`` and a ``prebuiltVoiceConfig`` voice name), same retry
    posture on 429/5xx. Dropped: pipeline-specific quota-marker parsing,
    usage-token accounting, and the per-language style-instruction table
    — an optional per-role ``style`` string (prepended to the text, in
    the "instruction:\\ntext" form Google recommends) is exposed instead,
    left empty by default so behavior stays generic.
    """

    sample_rate = DEFAULT_GEMINI_SAMPLE_RATE

    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_GEMINI_MODEL,
        style_map: dict[str, str] | None = None,
        temperature: float = 0.7,
        max_retries: int = 3,
        timeout: float = 120.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.style_map = style_map or {}
        self.temperature = temperature
        self.max_retries = max_retries
        self.timeout = timeout

    def synthesize(self, *, role: str, voice: str, text: str) -> bytes:
        style = self.style_map.get(role, "")
        payload_text = f"{style}\n{text}" if style else text
        payload = {
            "contents": [{"parts": [{"text": payload_text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "temperature": self.temperature,
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
            },
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        req_body = json.dumps(payload).encode()
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = json.loads(resp.read())
                return self._extract_pcm(body)
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:300]
                if e.code == 429 or e.code >= 500:
                    last_error = TTSError(f"gemini transient HTTP {e.code}: {detail}")
                    time.sleep(4.0 * (attempt + 1))
                    continue
                raise TTSError(f"gemini HTTP {e.code}: {detail}") from e
            except urllib.error.URLError as e:
                last_error = TTSError(f"gemini transport error: {e.reason}")
                time.sleep(4.0 * (attempt + 1))
        raise TTSError(f"gemini TTS failed after {self.max_retries} attempts: {last_error}")

    @staticmethod
    def _extract_pcm(body: dict) -> bytes:
        try:
            part = body["candidates"][0]["content"]["parts"][0]["inlineData"]
        except (KeyError, IndexError) as e:
            reason = (
                body.get("promptFeedback", {}).get("blockReason")
                or (body.get("candidates") or [{}])[0].get("finishReason")
                or "unknown"
            )
            raise TTSError(f"gemini TTS returned no audio (reason={reason})") from e
        return base64.b64decode(part["data"])


# ── Assembly ─────────────────────────────────────────────────────────────


@dataclass
class ChapterMark:
    """One chapter's start offset in the rendered episode."""

    title: str
    anchor: str | None
    start_ms: int

    def as_dict(self) -> dict:
        return {"title": self.title, "anchor": self.anchor, "start_ms": self.start_ms}


@dataclass
class CompiledEpisode:
    pcm: bytes
    sample_rate: int
    duration_ms: int
    total_chars: int
    tts_calls: int
    chapters: list[ChapterMark] = field(default_factory=list)


def pcm_silence(ms: int, sample_rate: int) -> bytes:
    """``ms`` milliseconds of digital silence, s16le mono at ``sample_rate``."""
    n_samples = int(sample_rate * ms / 1000)
    return b"\x00\x00" * n_samples


def pcm_duration_ms(pcm: bytes, sample_rate: int) -> float:
    n_samples = len(pcm) // 2  # 16-bit mono → 2 bytes/sample
    return 1000.0 * n_samples / sample_rate


def resolve_voice(role: str, voice_map: dict[str, str]) -> str:
    """Voice for a role: exact match, else the map's ``host`` entry, else
    its first value. Mirrors ``build_tts_chunks``'s default-voice fallback
    in the production pipeline, so an un-mapped role degrades gracefully
    instead of failing the whole run."""
    if role in voice_map:
        return voice_map[role]
    if "host" in voice_map:
        return voice_map["host"]
    if voice_map:
        return next(iter(voice_map.values()))
    raise TTSError(f"no voice configured for role '{role}' and --voice map is empty")


def compile_episode(
    doc: Document,
    provider: TTSProvider,
    *,
    voice_map: dict[str, str],
    turn_gap_ms: int,
    chapter_gap_ms: int,
    max_chars: int,
    on_progress=None,
) -> CompiledEpisode:
    """Synthesize every turn and mux them into one continuous PCM stream.

    Silence is inserted between turns: ``chapter_gap_ms`` when the chapter
    changes, ``turn_gap_ms`` otherwise (including the very first turn, so
    the episode doesn't start mid-breath). Chunks split out of the same
    over-long turn (see ``split_long_turn``) are concatenated with no gap —
    they are one utterance, not two turns.
    """
    rate = provider.sample_rate
    out = bytearray()
    chapters: list[ChapterMark] = []
    total_chars = 0
    tts_calls = 0
    t_ms = 0.0

    for i, turn in enumerate(doc.turns):
        new_chapter = i == 0 or turn.chapter != doc.turns[i - 1].chapter
        gap = chapter_gap_ms if new_chapter else turn_gap_ms
        out += pcm_silence(gap, rate)
        t_ms += gap

        if turn.chapter and (not chapters or chapters[-1].title != turn.chapter):
            chapters.append(ChapterMark(title=turn.chapter, anchor=turn.chapter_anchor, start_ms=int(t_ms)))

        voice = resolve_voice(turn.role, voice_map)
        for chunk in split_long_turn(turn.text, max_chars):
            if on_progress:
                on_progress(i, turn.role, len(chunk))
            pcm = provider.synthesize(role=turn.role, voice=voice, text=chunk)
            tts_calls += 1
            total_chars += len(chunk)
            out += pcm
            t_ms += pcm_duration_ms(pcm, rate)

    return CompiledEpisode(
        pcm=bytes(out),
        sample_rate=rate,
        duration_ms=int(t_ms),
        total_chars=total_chars,
        tts_calls=tts_calls,
        chapters=chapters,
    )


def write_wav(path: Path, pcm: bytes, sample_rate: int) -> None:
    """Write s16le mono PCM as a standard WAV file, stdlib only."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)


# ── CLI ──────────────────────────────────────────────────────────────────

DEFAULT_VOICE_MAP = {"host": "Kore", "signpost": "Charon"}
DEFAULT_TURN_GAP_MS = 700
DEFAULT_CHAPTER_GAP_MS = 1300
DEFAULT_MAX_CHARS = 2800


def _parse_kv_pairs(pairs: list[str], *, flag: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in pairs:
        if "=" not in p:
            raise SystemExit(f"{flag}: expected role=value, got '{p}'")
        role, _, value = p.partition("=")
        out[role.strip().lower()] = value.strip()
    return out


def _fmt_ms(ms: int) -> str:
    s, msec = divmod(ms, 1000)
    m, s = divmod(s, 60)
    return f"{m:02d}:{s:02d}.{msec:03d}"


def print_dry_run_plan(doc: Document, *, voice_map: dict[str, str], max_chars: int) -> None:
    print(f"title:   {doc.title or '(none)'}")
    print(f"lang:    {doc.lang or '(none)'}")
    print(f"turns:   {len(doc.turns)}")
    print(f"chars:   {doc.total_chars}")
    print(f"chapters: {len(doc.chapters)}")
    for title in doc.chapters:
        print(f"  - {title}")
    print()

    per_role: dict[str, tuple[int, int]] = {}  # role -> (turns, chars)
    for t in doc.turns:
        n, c = per_role.get(t.role, (0, 0))
        per_role[t.role] = (n + 1, c + len(t.text))
    print("roles:")
    for role in doc.roles:
        n, c = per_role[role]
        try:
            voice = resolve_voice(role, voice_map)
        except TTSError:
            voice = "(unmapped — will error at synthesis time)"
        print(f"  @{role:<12} turns={n:<4} chars={c:<6} voice={voice}")

    total_calls = sum(len(split_long_turn(t.text, max_chars)) for t in doc.turns)
    print()
    print(f"planned TTS calls: {total_calls} (max_chars={max_chars} per call)")
    print("\n(dry run — no network calls, no audio, no timing)")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="listen_compile.py",
        description="Parse a .listen.md file and synthesize it to a WAV episode.",
    )
    p.add_argument("input", type=Path, help="path to the .listen.md source file")
    p.add_argument("-o", "--output", type=Path, help="output .wav path (required unless --dry-run)")
    p.add_argument("--dry-run", action="store_true", help="parse and print the plan, no network calls")
    p.add_argument(
        "--voice", action="append", default=[], metavar="role=voice",
        help="voice binding for a role, repeatable (default: host=Kore, signpost=Charon)",
    )
    p.add_argument(
        "--style", action="append", default=[], metavar="role=text",
        help="optional spoken-delivery instruction prepended to a role's turns, repeatable",
    )
    p.add_argument("--chapters", type=Path, metavar="PATH", help="write chapter marks as JSON to this path")
    p.add_argument("--turn-gap-ms", type=int, default=DEFAULT_TURN_GAP_MS, help=f"silence between turns (default: {DEFAULT_TURN_GAP_MS})")
    p.add_argument("--chapter-gap-ms", type=int, default=DEFAULT_CHAPTER_GAP_MS, help=f"silence between chapters (default: {DEFAULT_CHAPTER_GAP_MS})")
    p.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS, help=f"split turns longer than this into multiple TTS calls (default: {DEFAULT_MAX_CHARS})")
    p.add_argument("--model", default=DEFAULT_GEMINI_MODEL, help=f"Gemini TTS model (default: {DEFAULT_GEMINI_MODEL})")
    p.add_argument("--temperature", type=float, default=0.7, help="Gemini TTS sampling temperature (default: 0.7)")
    p.add_argument("--api-key", help="Gemini API key (default: $GEMINI_API_KEY)")
    return p


def main(argv: list[str] | None = None) -> int:
    import os

    args = build_arg_parser().parse_args(argv)

    if not args.input.exists():
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 1

    doc = parse_listenmd(args.input.read_text(encoding="utf-8"))
    if not doc.turns:
        print("error: no speaker turns found — is this a valid .listen.md file?", file=sys.stderr)
        return 1

    voice_map = dict(DEFAULT_VOICE_MAP)
    voice_map.update(_parse_kv_pairs(args.voice, flag="--voice"))
    style_map = _parse_kv_pairs(args.style, flag="--style")

    if args.dry_run:
        print_dry_run_plan(doc, voice_map=voice_map, max_chars=args.max_chars)
        return 0

    if not args.output:
        print("error: -o/--output is required (or pass --dry-run)", file=sys.stderr)
        return 1

    api_key = args.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("error: no Gemini API key — pass --api-key or set $GEMINI_API_KEY", file=sys.stderr)
        return 1

    provider = GeminiTTSProvider(
        api_key, model=args.model, style_map=style_map, temperature=args.temperature,
    )

    def on_progress(turn_index: int, role: str, chars: int) -> None:
        print(f"[tts] turn {turn_index:03d} role={role} chars={chars}", file=sys.stderr)

    episode = compile_episode(
        doc,
        provider,
        voice_map=voice_map,
        turn_gap_ms=args.turn_gap_ms,
        chapter_gap_ms=args.chapter_gap_ms,
        max_chars=args.max_chars,
        on_progress=on_progress,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_wav(args.output, episode.pcm, episode.sample_rate)

    print(
        f"\nwrote {args.output} "
        f"({_fmt_ms(episode.duration_ms)}, {episode.total_chars} chars, {episode.tts_calls} TTS calls)"
    )
    print("chapters:")
    for c in episode.chapters:
        anchor = f" {{#{c.anchor}}}" if c.anchor else ""
        print(f"  {_fmt_ms(c.start_ms)}  {c.title}{anchor}")

    if args.chapters:
        args.chapters.write_text(json.dumps([c.as_dict() for c in episode.chapters], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nwrote chapter marks to {args.chapters}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
