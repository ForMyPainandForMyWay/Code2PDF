"""Generate a syntax-highlighted PDF for code files in a project.

Usage:
    python code_to_pdf.py <project_dir> <output_dir> [--font /path/to/font.(ttf|ttc)]

The script respects .gitignore by default (via `git ls-files`). Files are
ordered by relative path, each file starts on a new page, and highlighting
supports C / C++ / Python / CUDA out of the box. Provide a font that supports
Chinese (or other CJK) to avoid missing glyphs. The script will try common
system fonts automatically when --font is omitted.
"""
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern
from pygments.lexers import get_lexer_for_filename
from pygments.styles import get_style_by_name
from pygments.token import Token
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


CODE_EXTS = {
    ".py",
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hpp",
    ".cu",
    ".cuh",
    ".qml",
    ".html",
    ".htm",
    ".js",
    ".jsx",
    ".css",
}

# Light-friendly palette so normal text is readable on white background.
STYLE_NAME = "friendly"

# Preferred monospaced CJK-capable fonts (path, subfont index, registered name).
CJK_FONT_CANDIDATES: list[Tuple[Path, int, str]] = [
    (Path("/usr/share/fonts/truetype/sarasa-gothic/SarasaMonoSC-Regular.ttf"), 0, "SarasaMonoSC"),
    (Path("/usr/share/fonts/truetype/lxgw/LXGWWenKaiMono-Regular.ttf"), 0, "LXGWWenKaiMono"),
    (Path("/usr/share/fonts/truetype/noto/NotoSansMonoCJKsc-Regular.otf"), 0, "NotoSansMonoCJK"),
    (Path("/usr/share/fonts/opentype/noto/NotoSansMonoCJKsc-Regular.otf"), 0, "NotoSansMonoCJK"),
    (Path("/System/Library/Fonts/PingFang.ttc"), 0, "PingFang"),  # proportional but wide coverage
    (Path("/System/Library/Fonts/STHeiti Light.ttc"), 0, "STHeiti-Light"),
    (Path("/Library/Fonts/Arial Unicode.ttf"), 0, "ArialUnicode"),
    (Path("/Library/Fonts/SourceHanSansSC-Normal.otf"), 0, "SourceHanSansSC"),
    (Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"), 0, "NotoSansCJK"),
    (Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"), 0, "NotoSansCJK"),
    (Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"), 0, "WQYZenHei"),
    (Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"), 0, "WQYMicroHei"),
    (Path("C:/Windows/Fonts/msyh.ttc"), 0, "MicrosoftYaHei"),
    (Path("C:/Windows/Fonts/simhei.ttf"), 0, "SimHei"),
]


def load_gitignored_files(project_dir: Path, extra_excludes: Optional[set[str]] = None) -> List[Path]:
    """Return files under project_dir that are NOT ignored by .gitignore (best effort).

    We parse .gitignore rules from project_dir (plus .git/info/exclude if present).
    Matching is done relative to project_dir to honor anchored patterns.
    """

    pattern_lines: list[str] = []
    root_gitignore = project_dir / ".gitignore"
    if root_gitignore.exists():
        pattern_lines += root_gitignore.read_text().splitlines()
    info_exclude = project_dir / ".git" / "info" / "exclude"
    if info_exclude.exists():
        pattern_lines += info_exclude.read_text().splitlines()
    # Also honor git excludes at repo root if project_dir is a subdir of a repo.
    try:
        res = subprocess.run(
            ["git", "-C", str(project_dir), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
        repo_root = Path(res.stdout.strip())
        if repo_root != project_dir:
            shared_gitignore = repo_root / ".gitignore"
            if shared_gitignore.exists():
                pattern_lines += shared_gitignore.read_text().splitlines()
            shared_exclude = repo_root / ".git" / "info" / "exclude"
            if shared_exclude.exists():
                pattern_lines += shared_exclude.read_text().splitlines()
    except Exception:
        pass

    spec = PathSpec.from_lines(GitWildMatchPattern, pattern_lines)
    base = project_dir

    files: List[Path] = []
    normalized_excludes = {Path(p).as_posix().rstrip("/") for p in (extra_excludes or set())}

    for root, dirs, filenames in os.walk(project_dir):
        rel_root = Path(root).relative_to(base)
        # Remove ignored directories in-place to prune traversal.
        pruned_dirs = []
        for d in dirs:
            rel_dir = rel_root / d
            posix_dir = rel_dir.as_posix()
            if posix_dir in normalized_excludes or any(
                posix_dir.startswith(ex + "/") for ex in normalized_excludes
            ):
                continue
            if spec.match_file(posix_dir) or spec.match_file(posix_dir + "/"):
                continue
            pruned_dirs.append(d)
        dirs[:] = pruned_dirs

        for fname in filenames:
            rel_path = rel_root / fname
            posix_file = rel_path.as_posix()
            if spec.match_file(posix_file):
                continue
            files.append(Path(root) / fname)
    return files


def filter_code_files(files: Iterable[Path], base: Path) -> List[Path]:
    return sorted(
        [f for f in files if f.suffix.lower() in CODE_EXTS and f.is_file()],
        key=lambda p: str(p.relative_to(base)),
    )


def register_font(path: Path, name: Optional[str] = None, subfont: int = 0) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    font_name = name or path.stem
    pdfmetrics.registerFont(TTFont(font_name, str(path), subfontIndex=subfont))
    return font_name


def pick_font(preferred: Optional[Path], candidates: list[Tuple[Path, int, str]], fallback: str) -> str:
    if preferred:
        try:
            return register_font(preferred)
        except Exception as exc:
            raise SystemExit(f"Failed to load font {preferred}: {exc}") from exc

    for path, idx, name in candidates:
        if path.exists():
            try:
                return register_font(path, name, idx)
            except Exception:
                continue

    try:
        pdfmetrics.getFont(fallback)
        return fallback
    except KeyError:
        pdfmetrics.registerFont(TTFont(fallback, fallback))
        return fallback


def token_color(style, token_type):
    """Translate a pygments token into an RGB tuple understood by ReportLab."""

    style_def = style.style_for_token(token_type)
    hex_color = style_def.get("color")
    if hex_color:
        return colors.HexColor(f"#{hex_color}")
    return colors.black


def is_cjk(char: str) -> bool:
    code_point = ord(char)
    return (
        0x4E00 <= code_point <= 0x9FFF  # CJK Unified Ideographs
        or 0x3400 <= code_point <= 0x4DBF  # Extension A
        or 0x20000 <= code_point <= 0x2A6DF  # Extension B
        or 0x2A700 <= code_point <= 0x2B73F  # Extension C
        or 0x2B740 <= code_point <= 0x2B81F  # Extension D
        or 0x2B820 <= code_point <= 0x2CEAF  # Extension E
        or 0xF900 <= code_point <= 0xFAFF  # Compatibility Ideographs
    )


def split_font_runs(text: str, ascii_font: str, cjk_font: str) -> list[tuple[str, str]]:
    runs: list[tuple[str, str]] = []
    if not text:
        return runs
    current_font = cjk_font if is_cjk(text[0]) else ascii_font
    buffer = []
    for ch in text:
        font = cjk_font if is_cjk(ch) else ascii_font
        if font != current_font:
            runs.append(("".join(buffer), current_font))
            buffer = [ch]
            current_font = font
        else:
            buffer.append(ch)
    runs.append(("".join(buffer), current_font))
    return runs


def measure_pages_for_file(
    file_path: Path,
    page_width: float,
    page_height: float,
    margin_left: float,
    margin_right: float,
    margin_top: float,
    margin_bottom: float,
    font_ascii: str,
    font_cjk: str,
    font_size: int,
    show_line_numbers: bool = True,
) -> int:
    """Estimate how many pages the file will consume with current layout."""

    text = file_path.read_text(encoding="utf-8", errors="replace")
    total_lines = text.count("\n") + 1

    line_height = font_size * 1.4
    digits = max(3, len(str(total_lines)))
    gutter_spacing = 6
    gutter_width = (
        pdfmetrics.stringWidth("9" * digits, font_ascii, font_size) + gutter_spacing
        if show_line_numbers else 0
    )
    text_width_limit = page_width - margin_left - margin_right - gutter_width

    lexer = get_lexer_for_filename(file_path.name, stripall=False)
    y = page_height - margin_top - (line_height * 1.5)
    pages = 1
    x = margin_left + (gutter_width if show_line_numbers else 0)

    for token_type, token_value in lexer.get_tokens(text):
        segments = token_value.split("\n")
        for seg_idx, segment in enumerate(segments):
            if segment:
                pending = segment.replace("\t", "    ")
                while pending:
                    remaining = text_width_limit - (x - margin_left)
                    if remaining <= 0:
                        y -= line_height
                        if y < margin_bottom + line_height:
                            pages += 1
                            y = page_height - margin_top - (line_height * 1.5)
                        x = margin_left + (gutter_width if show_line_numbers else 0)
                        remaining = text_width_limit - (x - margin_left)

                    width = 0.0
                    split_at = 0
                    for idx, ch in enumerate(pending):
                        font_for_char = font_cjk if is_cjk(ch) else font_ascii
                        w = pdfmetrics.stringWidth(ch, font_for_char, font_size)
                        if width + w > remaining and idx > 0:
                            break
                        width += w
                        split_at = idx + 1
                    if split_at == 0:
                        split_at = 1
                    chunk = pending[:split_at]
                    pending = pending[split_at:]

                    x += pdfmetrics.stringWidth(chunk, font_ascii, font_size)

                    if pending:
                        y -= line_height
                        if y < margin_bottom + line_height:
                            pages += 1
                            y = page_height - margin_top - (line_height * 1.5)
                        x = margin_left + (gutter_width if show_line_numbers else 0)

            if seg_idx < len(segments) - 1:
                y -= line_height
                if y < margin_bottom + line_height:
                    pages += 1
                    y = page_height - margin_top - (line_height * 1.5)
                x = margin_left + (gutter_width if show_line_numbers else 0)

    return pages


def measure_toc_pages(
    entries: list[dict],
    page_width: float,
    page_height: float,
    margin_left: float,
    margin_right: float,
    margin_top: float,
    margin_bottom: float,
    font_ascii: str,
    font_size: int,
) -> int:
    line_height = font_size * 1.4
    usable_height = page_height - margin_top - margin_bottom - (line_height * 1.5)  # title + gap
    lines_per_page = max(1, int(usable_height // line_height))
    total_lines = 1 + sum(1 if not e.get("is_header") else 1 for e in entries)
    pages = (total_lines + lines_per_page - 1) // lines_per_page
    return pages


def draw_toc(
    canv: canvas.Canvas,
    entries: list[dict],
    page_width: float,
    page_height: float,
    margin_left: float,
    margin_right: float,
    margin_top: float,
    margin_bottom: float,
    font_ascii: str,
    font_cjk: str,
    font_size: int,
    columns: int = 1,
    global_page_start: int = 1,
    global_total_pages: int = 1,
) -> int:
    line_height = font_size * 1.4
    y = page_height - margin_top - (line_height * 0.5)

    def draw_footer(global_page: int):
        global_font_size = font_size + 1
        global_text = f"{global_page}/{global_total_pages}"
        global_width = pdfmetrics.stringWidth(global_text, font_ascii, global_font_size)
        footer_y = max(font_size, margin_bottom * 0.6)
        canv.setFont(font_ascii, global_font_size)
        canv.setFillColor(colors.grey)
        canv.drawString((page_width - global_width) / 2, footer_y, global_text)

    canv.setFont(font_cjk, font_size + 4)
    canv.setFillColor(colors.darkblue)
    canv.drawString(margin_left, y, "目录")
    draw_footer(global_page_start)
    y -= line_height * 1.5
    canv.setFont(font_ascii, font_size)
    page_idx = global_page_start

    first_entry = True
    for entry in entries:
        name = entry["label"]
        start_page = entry["page"]
        dest = entry.get("dest")
        toc_dest = entry.get("toc_dest")
        is_header = entry.get("is_header", False)
        if y < margin_bottom + line_height:
            canv.showPage()
            page_idx += 1
            canv.setFont(font_cjk, font_size + 4)
            canv.setFillColor(colors.darkblue)
            y = page_height - margin_top - (line_height * 0.5)
            canv.drawString(margin_left, y, "目录")
            draw_footer(page_idx)
            y -= line_height * 1.5
            canv.setFont(font_ascii, font_size)

        if is_header and not first_entry:
            y -= line_height * 0.4  # extra gap before a new group header

        canv.setFillColor(colors.black)
        canv.setFont(font_cjk if not is_header else font_cjk, font_size + (2 if is_header else 0))
        canv.drawString(margin_left, y, name)
        if not is_header:
            # Bookmark for linking back from file header to this entry
            if toc_dest:
                canv.bookmarkHorizontal(toc_dest, margin_left, y)
            pg_text = str(start_page)
            pg_width = pdfmetrics.stringWidth(pg_text, font_ascii, font_size)
            canv.setFont(font_ascii, font_size)
            canv.drawString(page_width - margin_right - pg_width, y, pg_text)
            # Clickable area for hyperlink.
            name_width = pdfmetrics.stringWidth(name, font_cjk, font_size)
            canv.linkAbsolute(
                "",
                dest,
                Rect=(
                    margin_left,
                    y - line_height * 0.2,
                    margin_left + name_width,
                y + line_height * 0.8,
                ),
                thickness=0,
            )
        y -= line_height * (1.4 if is_header else 1.0)
        first_entry = False

    return page_idx - global_page_start + 1


def build_toc_entries(
    files: list[Path],
    project_dir: Path,
    dest_names: list[str],
    toc_dest_names: list[str],
    start_pages: list[int],
    mode: str = "auto",
) -> list[dict]:
    rels = [f.relative_to(project_dir) for f in files]
    depths = [len(p.parts) for p in rels]
    avg_depth = sum(depths) / len(depths) if depths else 0

    if mode == "auto":
        mode = "grouped" if len(files) > 120 or avg_depth > 3 else "flat"

    entries: list[dict] = []
    if mode == "grouped":
        groups: dict[str, list[tuple[str, int]]] = {}
        for idx, rel in enumerate(rels):
            parts = rel.parts
            group = parts[0] if len(parts) > 1 else "(root)"
            tail = "/".join(parts[1:]) if len(parts) > 1 else parts[0]
            groups.setdefault(group, []).append((tail, idx))
        for group in sorted(groups.keys()):
            first_idx = groups[group][0][1]
            entries.append({"label": group, "page": start_pages[first_idx], "is_header": True})
            for tail, idx in sorted(groups[group], key=lambda t: t[0]):
                entries.append(
                    {
                        "label": tail,
                        "page": start_pages[idx],
                        "dest": dest_names[idx],
                        "toc_dest": toc_dest_names[idx],
                        "is_header": False,
                    }
                )
    else:  # flat
        for idx, rel in enumerate(rels):
            entries.append(
                {
                    "label": rel.as_posix(),
                    "page": start_pages[idx],
                    "dest": dest_names[idx],
                    "toc_dest": toc_dest_names[idx],
                    "is_header": False,
                }
            )
    return entries


def draw_highlighted_file(
    canv: canvas.Canvas,
    style,
    file_path: Path,
    rel_path: Path,
    page_width: float,
    page_height: float,
    margin_left: float = 36.0,
    margin_right: float = 20.0,
    margin_top: float = 36.0,
    margin_bottom: float = 36.0,
    font_ascii: str = "Courier",
    font_cjk: str = "Courier",
    font_size: int = 9,
    show_line_numbers: bool = True,
    file_page_total: int = 1,
    global_page_start: int = 1,
    global_total_pages: int = 1,
    dest_name: Optional[str] = None,
    toc_link: Optional[str] = None,
):
    """Render one file on the current page of the canvas.

    Returns how many pages were consumed for this file.
    """

    text = file_path.read_text(encoding="utf-8", errors="replace")
    total_lines = text.count("\n") + 1

    line_height = font_size * 1.4
    digits = max(3, len(str(total_lines)))
    gutter_spacing = 6
    gutter_width = (
        pdfmetrics.stringWidth("9" * digits, font_ascii, font_size) + gutter_spacing
        if show_line_numbers else 0
    )
    text_width_limit = page_width - margin_left - margin_right - gutter_width

    header_text_current = str(rel_path)
    header_filename_only = file_path.name

    header_font_size = font_size + 3
    page_num_font_size = font_size + 3
    file_page_idx = 1
    global_page = global_page_start
    toc_dest_name = toc_link or f"toc_{rel_path.as_posix().replace('/', '_')}"

    def draw_header():
        # left: header text; right: page number
        canv.setFont(font_ascii, header_font_size)
        canv.setFillColor(colors.darkblue)
        header_y = page_height - margin_top
        canv.drawString(margin_left, header_y, header_text_current)
        header_width = pdfmetrics.stringWidth(header_text_current, font_ascii, header_font_size)
        # Clickable header link target differs for first vs. subsequent pages
        if file_page_idx == 1:
            # link back to TOC entry
            canv.linkAbsolute(
                "",
                toc_dest_name,
                Rect=(
                    margin_left,
                    header_y - header_font_size * 0.2,
                    margin_left + header_width,
                    header_y + header_font_size * 0.8,
                ),
                thickness=0,
            )
        else:
            # link to file first page bookmark
            if dest_name:
                canv.linkAbsolute(
                    "",
                    dest_name,
                    Rect=(
                        margin_left,
                        header_y - header_font_size * 0.2,
                        margin_left + header_width,
                        header_y + header_font_size * 0.8,
                    ),
                    thickness=0,
                )

        pg_text = f"{file_page_idx}/{file_page_total}"
        canv.setFont(font_ascii, page_num_font_size)
        canv.setFillColor(colors.grey)
        pg_width = pdfmetrics.stringWidth(pg_text, font_ascii, page_num_font_size)
        canv.drawString(page_width - margin_right - pg_width, page_height - margin_top, pg_text)

        # Footer: global page numbers centered at bottom.
        global_text = f"{global_page}/{global_total_pages}"
        global_font_size = font_size + 1
        global_width = pdfmetrics.stringWidth(global_text, font_ascii, global_font_size)
        footer_y = max(font_size, margin_bottom * 0.6)
        canv.setFont(font_ascii, global_font_size)
        canv.setFillColor(colors.grey)
        canv.drawString((page_width - global_width) / 2, footer_y, global_text)

    y = page_height - margin_top - (line_height * 1.5)
    draw_header()
    if dest_name:
        canv.bookmarkPage(dest_name)

    lexer = get_lexer_for_filename(file_path.name, stripall=False)
    line_no = 1
    x = margin_left

    def start_line(current_line_no: int, show_number: bool = True):
        nonlocal x, y, header_text_current, file_page_idx, global_page
        if y < margin_bottom + line_height:
            canv.showPage()
            header_text_current = header_filename_only
            file_page_idx += 1
            global_page += 1
            y = page_height - margin_top - (line_height * 1.5)
            draw_header()
        x = margin_left
        if show_line_numbers:
            canv.setFillColor(colors.grey)
            canv.setFont(font_ascii, font_size)
            ln_text = f"{current_line_no:>{digits}}" if show_number else " " * digits
            canv.drawString(x, y, ln_text)
            x += gutter_width
        # Caller will set token color after this when drawing content.

    start_line(line_no)

    for token_type, token_value in lexer.get_tokens(text):
        col = token_color(style, token_type)
        canv.setFillColor(col)

        # Handle newlines explicitly to keep lexer state intact across lines.
        segments = token_value.split("\n")
        for seg_idx, segment in enumerate(segments):
            if segment:
                pending = segment.replace("\t", "    ")
                while pending:
                    remaining = text_width_limit - (x - margin_left)
                    if remaining <= 0:
                        y -= line_height
                        start_line(line_no, show_number=False)
                        canv.setFillColor(col)
                        remaining = text_width_limit - (x - margin_left)

                    width = 0.0
                    split_at = 0
                    for idx, ch in enumerate(pending):
                        font_for_char = font_cjk if is_cjk(ch) else font_ascii
                        w = pdfmetrics.stringWidth(ch, font_for_char, font_size)
                        if width + w > remaining and idx > 0:
                            break
                        width += w
                        split_at = idx + 1

                    if split_at == 0:
                        split_at = 1  # ensure progress

                    chunk = pending[:split_at]
                    pending = pending[split_at:]

                    for run_text, run_font in split_font_runs(chunk, font_ascii, font_cjk):
                        canv.setFont(run_font, font_size)
                        canv.drawString(x, y, run_text)
                        x += pdfmetrics.stringWidth(run_text, run_font, font_size)

                    if pending:
                        y -= line_height
                        start_line(line_no, show_number=False)
                        canv.setFillColor(col)

            if seg_idx < len(segments) - 1:
                # explicit newline
                y -= line_height
                line_no += 1
                start_line(line_no)
                canv.setFillColor(col)

    return file_page_idx


def build_pdf(
    project_dir: Path,
    output_dir: Path,
    font_file: Optional[Path] = None,
    cjk_font_file: Optional[Path] = None,
    split_files: bool = False,
    extra_excludes: Optional[set[str]] = None,
    toc_mode: str = "auto",
) -> Path:
    files = filter_code_files(load_gitignored_files(project_dir, extra_excludes), project_dir)
    if not files:
        raise SystemExit("No code files found after applying .gitignore filters.")

    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"{project_dir.name}.pdf"
    per_file_dir = output_dir / "files"
    if split_files:
        per_file_dir.mkdir(parents=True, exist_ok=True)

    font_ascii = pick_font(font_file, [], "Courier")
    font_cjk = pick_font(cjk_font_file, CJK_FONT_CANDIDATES, font_ascii)
    canv = canvas.Canvas(str(pdf_path), pagesize=A4)
    page_width, page_height = A4
    style = get_style_by_name(STYLE_NAME)

    file_page_counts = []
    dest_names = []
    toc_dest_names = []
    for fp in files:
        rel = fp.relative_to(project_dir)
        dest_names.append(f"dest_{rel.as_posix().replace('/', '_')}")
        toc_dest_names.append(f"toc_{rel.as_posix().replace('/', '_')}")
        file_page_counts.append(
            measure_pages_for_file(
                fp,
                page_width,
                page_height,
                36.0,
                20.0,
                36.0,
                36.0,
                font_ascii,
                font_cjk,
                9,
            )
        )
    temp_entries = build_toc_entries(
        files,
        project_dir,
        dest_names,
        toc_dest_names,
        [0] * len(files),
        mode=toc_mode,
    )
    toc_pages = measure_toc_pages(
        temp_entries,
        page_width,
        page_height,
        36.0,
        20.0,
        36.0,
        36.0,
        font_ascii,
        9,
    )
    total_pages = toc_pages + sum(file_page_counts)

    # TOC: compute starting page for each file (global)
    start_pages = []
    cursor = toc_pages + 1
    for count in file_page_counts:
        start_pages.append(cursor)
        cursor += count

    # Render TOC
    toc_entries = build_toc_entries(
        files,
        project_dir,
        dest_names,
        toc_dest_names,
        start_pages,
        mode=toc_mode,
    )
    draw_toc(
        canv,
        toc_entries,
        page_width,
        page_height,
        36.0,
        20.0,
        36.0,
        36.0,
        font_ascii,
        font_cjk,
        9,
        global_page_start=1,
        global_total_pages=total_pages,
    )
    global_page_start = toc_pages + 1

    for idx, file_path in enumerate(files):
        canv.showPage()
        rel_path = file_path.relative_to(project_dir)
        draw_highlighted_file(
            canv,
            style,
            file_path,
            rel_path,
            page_width,
            page_height,
            margin_left=36.0,
            margin_right=20.0,
            margin_top=36.0,
            margin_bottom=36.0,
            font_ascii=font_ascii,
            font_cjk=font_cjk,
            file_page_total=file_page_counts[idx],
            global_page_start=global_page_start,
            global_total_pages=total_pages,
            dest_name=dest_names[idx],
            toc_link=toc_dest_names[idx],
        )
        global_page_start += file_page_counts[idx]
        if split_files:
            single_pdf = per_file_dir / f"{rel_path.name}.pdf"
            single_canvas = canvas.Canvas(str(single_pdf), pagesize=A4)
            draw_highlighted_file(
                single_canvas,
                style,
                file_path,
                rel_path,
                page_width,
                page_height,
                margin_left=36.0,
                margin_right=20.0,
                margin_top=36.0,
                margin_bottom=36.0,
                font_ascii=font_ascii,
                font_cjk=font_cjk,
                file_page_total=file_page_counts[idx],
                global_page_start=1,
                global_total_pages=file_page_counts[idx],
                dest_name=dest_names[idx],
                toc_link=None,
            )
            single_canvas.save()

    canv.save()
    return pdf_path


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path, help="Path to the project root")
    parser.add_argument("output_dir", type=Path, help="Directory to place the PDF")
    parser.add_argument(
        "--font",
        type=Path,
        help="TTF/TTC font file to embed (use one that supports Chinese/CJK)",
    )
    parser.add_argument(
        "--cjk-font",
        type=Path,
        help="Optional CJK-only font; ASCII will use --font or Courier, CJK uses this.",
    )
    parser.add_argument(
        "--split-files",
        action="store_true",
        help="Also emit individual PDFs per code file into <output>/files/ (off by default).",
    )
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Extra directories (relative to project_dir) to exclude in addition to .gitignore. Can be used multiple times.",
    )
    parser.add_argument(
        "--toc-mode",
        choices=["auto", "flat", "grouped"],
        default="auto",
        help="TOC layout: auto (default), flat list, or grouped by top-level directory.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    project_dir: Path = args.project_dir.expanduser().resolve()
    output_dir: Path = args.output_dir.expanduser().resolve()
    font_file: Optional[Path] = args.font.expanduser().resolve() if args.font else None
    cjk_font_file: Optional[Path] = args.cjk_font.expanduser().resolve() if args.cjk_font else None

    if not project_dir.exists() or not project_dir.is_dir():
        raise SystemExit(f"Project path not found or not a directory: {project_dir}")

    pdf_path = build_pdf(
        project_dir,
        output_dir,
        font_file=font_file,
        cjk_font_file=cjk_font_file,
        split_files=args.split_files,
        extra_excludes=set(args.exclude_dir),
        toc_mode=args.toc_mode,
    )
    print(f"PDF written to: {pdf_path}")


if __name__ == "__main__":
    main()
