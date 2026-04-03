"""
Generate spoken audio of Melito's Peri Pascha using Gemini TTS.

Reads the simplified Greek text, groups lines into chunks matching
the speech-{start}-{end}.wav naming convention, skips existing files.

Requires: GOOGLE_API_KEY environment variable set.
Usage:    python tts_generate.py
"""

import os
import sys
import wave
import time
from pathlib import Path

from google import genai
from google.genai import types

# --- Config ---
INPUT_FILE = "clean_greek_full_simple.txt"
OUTPUT_DIR = Path(".")
MODEL = "gemini-2.5-flash-preview-tts"
VOICE = "Charon"
SAMPLE_RATE = 22500
TARGET_CHUNK_LINES = 30  # approximate lines per audio file

SYSTEM_PROMPT = """\
You are reading an Ancient Greek liturgical homily aloud.
Read the Greek text with a dignified, measured pace.
Pause briefly at line breaks, longer between paragraphs.
The text is rhetorical — honor the parallelism and antithesis.
Pronounce clearly and naturally as Greek.\
"""


def wave_file(filename: str, pcm: bytes, channels: int = 1,
              rate: int = SAMPLE_RATE, sample_width: int = 2) -> None:
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)


def read_wave_data(filename: str) -> bytes:
    with wave.open(filename, "rb") as wf:
        return wf.readframes(wf.getnframes())


def build_chunks(path: str, target: int = TARGET_CHUNK_LINES) -> list[tuple[int, int, str]]:
    """Group lines into chunks of ~target lines, breaking at blank lines.

    Returns list of (start_line, end_line, text).
    """
    all_lines = Path(path).read_text(encoding="utf-8").split("\n")

    # First, find sections (groups of non-blank lines)
    sections: list[tuple[int, int, list[str]]] = []
    start = None
    buf: list[str] = []
    for i, line in enumerate(all_lines, 1):
        if line.strip():
            if start is None:
                start = i
            buf.append(line)
        else:
            if start is not None:
                sections.append((start, i - 1, buf))
                start = None
                buf = []
    if start is not None:
        sections.append((start, len(all_lines), buf))

    # Merge sections into chunks of ~target lines
    chunks: list[tuple[int, int, str]] = []
    chunk_start = None
    chunk_end = None
    chunk_lines: list[str] = []
    chunk_count = 0

    for s_start, s_end, s_lines in sections:
        n = len(s_lines)

        # If adding this section exceeds target and we already have content,
        # flush current chunk first
        if chunk_count > 0 and chunk_count + n > target:
            chunks.append((chunk_start, chunk_end, "\n".join(chunk_lines)))
            chunk_start = None
            chunk_lines = []
            chunk_count = 0

        if chunk_start is None:
            chunk_start = s_start
        chunk_end = s_end
        if chunk_lines:
            chunk_lines.append("")  # blank line between sections
        chunk_lines.extend(s_lines)
        chunk_count += n

    # Flush remaining
    if chunk_lines and chunk_start is not None:
        chunks.append((chunk_start, chunk_end, "\n".join(chunk_lines)))

    return chunks


def generate_section_audio(client: genai.Client, text: str, max_retries: int = 3) -> bytes:
    prompt = f"{SYSTEM_PROMPT}\n\nRead this aloud:\n\n{text}"

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=VOICE,
                            )
                        )
                    ),
                ),
            )
            return response.candidates[0].content.parts[0].inline_data.data
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 5 * (attempt + 1)
                print(f"retry {attempt + 1}/{max_retries} in {wait}s ...", end=" ", flush=True)
                time.sleep(wait)
            else:
                raise


def combine_wav_files(output_path: str, wav_files: list[str],
                      silence_seconds: float = 1.5,
                      rate: int = SAMPLE_RATE, sample_width: int = 2) -> None:
    silence = b"\x00" * int(rate * sample_width * silence_seconds)
    all_pcm = bytearray()

    for i, f in enumerate(wav_files):
        all_pcm.extend(read_wave_data(f))
        if i < len(wav_files) - 1:
            all_pcm.extend(silence)

    wave_file(output_path, bytes(all_pcm), rate=rate, sample_width=sample_width)


def find_existing_coverage() -> list[tuple[int, int, str]]:
    """Find all existing speech-*.wav files and their line ranges."""
    existing: list[tuple[int, int, str]] = []
    for f in Path(OUTPUT_DIR).glob("speech-*.wav"):
        parts = f.stem.replace("speech-", "").split("-")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            existing.append((int(parts[0]), int(parts[1]), str(f)))
    return sorted(existing)


def main() -> None:
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    all_lines = Path(INPUT_FILE).read_text(encoding="utf-8").split("\n")
    total_lines = len(all_lines)

    # Find what's already covered
    existing = find_existing_coverage()
    covered: set[int] = set()
    wav_files: list[str] = []
    for start, end, path in existing:
        for line in range(start, end + 1):
            covered.add(line)
        wav_files.append(path)

    print(f"Total lines: {total_lines}")
    print(f"Already covered: {len(covered)} lines in {len(existing)} files")

    if len(covered) >= total_lines - 5:  # allow a few blank lines
        print("All lines covered! Just combining.")
    else:
        # Find uncovered ranges and chunk them
        uncovered_start = max(covered) + 1 if covered else 1
        print(f"Generating from line {uncovered_start} onwards...")

        # Build chunks only for uncovered lines
        # Write a temp file with just the remaining lines
        remaining_lines = all_lines[uncovered_start - 1:]
        remaining_text = "\n".join(remaining_lines)

        # Parse into sections from the remaining text
        sections: list[tuple[int, int, list[str]]] = []
        start = None
        buf: list[str] = []
        for i, line in enumerate(remaining_lines, uncovered_start):
            if line.strip():
                if start is None:
                    start = i
                buf.append(line)
            else:
                if start is not None:
                    sections.append((start, i - 1, buf))
                    start = None
                    buf = []
        if start is not None:
            sections.append((start, uncovered_start + len(remaining_lines) - 1, buf))

        # Merge into chunks
        chunks: list[tuple[int, int, str]] = []
        chunk_start = None
        chunk_end = None
        chunk_lines: list[str] = []
        chunk_count = 0

        for s_start, s_end, s_lines in sections:
            n = len(s_lines)
            if chunk_count > 0 and chunk_count + n > TARGET_CHUNK_LINES:
                if chunk_start is not None:
                    chunks.append((chunk_start, chunk_end, "\n".join(chunk_lines)))
                chunk_start = None
                chunk_lines = []
                chunk_count = 0

            if chunk_start is None:
                chunk_start = s_start
            chunk_end = s_end
            if chunk_lines:
                chunk_lines.append("")
            chunk_lines.extend(s_lines)
            chunk_count += n

        if chunk_lines and chunk_start is not None:
            chunks.append((chunk_start, chunk_end, "\n".join(chunk_lines)))

        print(f"Sections to generate: {len(chunks)}")

        for i, (start, end, text) in enumerate(chunks):
            filename = f"speech-{start}-{end}.wav"
            out_path = OUTPUT_DIR / filename
            nlines = end - start + 1

            print(f"  [{i+1}/{len(chunks)}] lines {start}-{end} ({nlines} lines, {len(text)} chars) ...",
                  end=" ", flush=True)

            try:
                pcm = generate_section_audio(client, text)
                wave_file(str(out_path), pcm)
                wav_files.append(str(out_path))
                print(f"OK → {filename}")
            except Exception as e:
                print(f"FAILED: {e}")
                continue

            time.sleep(3)

    # Combine all files in line order
    all_wavs = find_existing_coverage()
    if all_wavs:
        combined = OUTPUT_DIR / "peri_pascha_full.wav"
        ordered = [path for _, _, path in all_wavs]
        print(f"\nCombining {len(ordered)} files → {combined}")
        combine_wav_files(str(combined), ordered)
        print(f"Done! Full audio: {combined}")


if __name__ == "__main__":
    main()
