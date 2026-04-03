"""CLI entry point for the Melito OCR pipeline."""

import sys
from pathlib import Path

import click

from melito.ocr import check_tesseract_lang, ocr_image
from melito.postprocess import postprocess
from melito.preprocess import preprocess
from melito.transliterate import transliterate_file


SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def collect_images(input_dir: Path) -> list[Path]:
    """Gather and sort image files from *input_dir*."""
    images = [p for p in input_dir.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS]
    if not images:
        click.echo(f"No image files found in {input_dir}", err=True)
        sys.exit(1)
    return sorted(images)


@click.command()
@click.argument("input_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("-o", "--output-dir", type=click.Path(path_type=Path), default=Path("output"),
              help="Directory for output text files (default: ./output).")
@click.option("--debug", is_flag=True, help="Save preprocessed debug images.")
@click.option("--combined/--no-combined", default=True, show_default=True,
              help="Also write a combined greek_clean.txt.")
def main(
    input_dir: Path,
    output_dir: Path,
    debug: bool,
    combined: bool,
) -> None:
    """Melito — extract polytonic Ancient Greek from scholarly edition page images.

    INPUT_DIR is a folder of page images (PNG, JPG, TIFF).
    Output requires manual trimming of headers, footnotes, and line numbers.
    """
    check_tesseract_lang()

    output_dir.mkdir(parents=True, exist_ok=True)
    debug_dir = output_dir / "debug" if debug else None

    images = collect_images(input_dir)
    click.echo(f"Found {len(images)} images in {input_dir}")

    all_pages: list[str] = []

    with click.progressbar(images, label="Processing pages") as bar:
        for img_path in bar:
            pil_img = preprocess(img_path, debug_dir=debug_dir)
            raw_lines = ocr_image(pil_img)
            raw_text = "\n".join(raw_lines)
            clean = postprocess(raw_text)

            page_file = output_dir / f"{img_path.stem}.txt"
            page_file.write_text(clean, encoding="utf-8")
            all_pages.append(clean)

    if combined:
        combined_path = output_dir / "greek_clean.txt"
        combined_path.write_text("\n\n".join(all_pages), encoding="utf-8")
        click.echo(f"Combined output → {combined_path}")

    click.echo(f"Done. {len(images)} pages → {output_dir}/")


@click.command("tts-prep")
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), default=None,
              help="Output file path (default: <input>_phonetic.txt or _simple.txt).")
@click.option("--mode", type=click.Choice(["latin", "greek"]), default="greek",
              help="'greek' = simplified Greek alphabet (best for Gemini). "
                   "'latin' = full Latin phonetic transliteration.")
def tts_prep(input_file: Path, output: Path | None, mode: str) -> None:
    """Prepare Greek text for TTS engines.

    --mode greek  (default): strips diacritics/breathing, keeps Greek letters.
    --mode latin: full Latin-alphabet transliteration (2nd c. Koine, Sardis).
    """
    if output is None:
        suffix = "_simple.txt" if mode == "greek" else "_phonetic.txt"
        output = input_file.with_name(input_file.stem + suffix)
    transliterate_file(str(input_file), str(output), mode=mode)
    click.echo(f"TTS output ({mode}) → {output}")
