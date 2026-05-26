from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "utf-16")
ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['_-][A-Za-z0-9]+)*")
CJK_TOKEN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]{2,}")
CAMEL_PART_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z0-9]|\b)|[A-Z]?[a-z]+|[0-9]+")
SAFE_NAME_RE = re.compile(r"[^\w.-]+", re.UNICODE)
GLOSSARY_DATA_COLUMNS = 4
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "between",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "each",
    "even",
    "for",
    "from",
    "had",
    "has",
    "have",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "may",
    "more",
    "most",
    "no",
    "not",
    "of",
    "on",
    "once",
    "one",
    "or",
    "other",
    "our",
    "out",
    "per",
    "same",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "time",
    "to",
    "too",
    "under",
    "until",
    "up",
    "use",
    "used",
    "using",
    "very",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "will",
    "with",
    "within",
    "without",
    "would",
    "you",
    "your",
    "align",
    "args",
    "center",
    "file",
    "format",
    "icon",
    "image",
    "left",
    "link",
    "named",
    "none",
    "png",
    "reason",
    "right",
    "section",
    "sort",
    "stub",
    "summary",
    "table",
    "template",
    "title",
    "version",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="按指定文本筛选术语表，输出仅包含相关术语的新 CSV。"
    )
    parser.add_argument("source_file", help="文本来源文件，例如 1.txt")
    parser.add_argument(
        "-g",
        "--glossary",
        default="translations.csv",
        help="要筛选的术语表 CSV，默认 translations.csv。",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="输出 CSV 路径。未指定时自动生成包含来源文件名的新文件。",
    )
    parser.add_argument(
        "--min-word-length",
        type=int,
        default=2,
        help="保留英文词的最短长度，默认 2。",
    )
    parser.add_argument(
        "--keep-stopwords",
        action="store_true",
        help="不过滤常见英文虚词。",
    )
    return parser.parse_args()


def read_text(path: Path) -> str:
    last_error: UnicodeError | None = None
    for encoding in TEXT_ENCODINGS:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeError as exc:
            last_error = exc

    raise UnicodeError(f"无法识别文件编码: {path}") from last_error


def should_keep_token(token: str, min_word_length: int, keep_stopwords: bool) -> bool:
    if not token or token.isdigit():
        return False

    if any("\u3400" <= char <= "\u9fff" for char in token):
        return len(token) >= 2

    if len(token) < min_word_length:
        return False

    return keep_stopwords or token not in STOPWORDS


def expand_ascii_token(token: str) -> set[str]:
    candidates = set()
    stripped = token.strip("._-'")
    if not stripped:
        return candidates

    candidates.add(stripped.casefold())
    candidates.update(piece.casefold() for piece in re.split(r"[_'-]+", stripped) if piece)
    candidates.update(piece.casefold() for piece in CAMEL_PART_RE.findall(stripped) if piece)
    return candidates


def extract_tokens(text: str, min_word_length: int, keep_stopwords: bool) -> set[str]:
    tokens: set[str] = set()

    for token in ASCII_TOKEN_RE.findall(text):
        for candidate in expand_ascii_token(token):
            if should_keep_token(candidate, min_word_length, keep_stopwords):
                tokens.add(candidate)

    for token in CJK_TOKEN_RE.findall(text):
        if should_keep_token(token, min_word_length, keep_stopwords):
            tokens.add(token)

    return tokens


def iter_rows(glossary_path: Path) -> tuple[list[list[str]], list[list[str]]]:
    with glossary_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        metadata_rows: list[list[str]] = []
        data_rows: list[list[str]] = []

        for row in csv.reader(csv_file):
            if not row:
                continue

            cleaned_row = [field.strip() for field in row]
            if len(cleaned_row) == GLOSSARY_DATA_COLUMNS:
                data_rows.append(cleaned_row)
            else:
                metadata_rows.append(cleaned_row)

    return metadata_rows, data_rows


def row_matches(
    row: list[str],
    source_tokens: set[str],
    min_word_length: int,
    keep_stopwords: bool,
) -> bool:
    for field in row[:2]:
        field_tokens = extract_tokens(field, min_word_length, keep_stopwords)
        if field_tokens and field_tokens.issubset(source_tokens):
            return True

    return False


def build_output_path(source_path: Path, glossary_path: Path, output_arg: str | None) -> Path:
    if output_arg:
        return Path(output_arg).resolve()

    safe_source_name = SAFE_NAME_RE.sub("_", source_path.stem).strip("._") or "source"
    return glossary_path.with_name(f"{glossary_path.stem}_{safe_source_name}{glossary_path.suffix}")


def main() -> int:
    args = parse_args()
    source_path = Path(args.source_file).resolve()
    glossary_path = Path(args.glossary).resolve()
    output_path = build_output_path(source_path, glossary_path, args.output)

    if not source_path.is_file():
        print(f"来源文件不存在: {source_path}", file=sys.stderr)
        return 1

    if not glossary_path.is_file():
        print(f"术语表不存在: {glossary_path}", file=sys.stderr)
        return 1

    source_tokens = extract_tokens(
        read_text(source_path),
        min_word_length=args.min_word_length,
        keep_stopwords=args.keep_stopwords,
    )
    metadata_rows, rows = iter_rows(glossary_path)
    matched_rows = [
        row
        for row in rows
        if row_matches(
            row,
            source_tokens,
            min_word_length=args.min_word_length,
            keep_stopwords=args.keep_stopwords,
        )
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerows(metadata_rows)
        writer.writerows(matched_rows)

    print(
        f"已从 {source_path.name} 提取 {len(source_tokens)} 个有效词，"
        f"匹配到 {len(matched_rows)} / {len(rows)} 行，输出: {output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())