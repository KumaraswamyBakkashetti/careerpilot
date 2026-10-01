import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import PurePath

from docx import Document
from pypdf import PdfReader

from app.modules.knowledge.models import Entity, normalize_alias
from app.modules.student.models import NormalizationStatus, Section

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PARSER_VERSION = "resume-parser-v1"
HEADINGS: dict[str, Section] = {
    "skills": "SKILLS",
    "technical skills": "SKILLS",
    "core skills": "SKILLS",
    "projects": "PROJECTS",
    "personal projects": "PROJECTS",
    "academic projects": "PROJECTS",
    "experience": "EXPERIENCE",
    "work experience": "EXPERIENCE",
    "employment": "EXPERIENCE",
    "education": "EDUCATION",
    "academic background": "EDUCATION",
    "certifications": "CERTIFICATIONS",
    "certificates": "CERTIFICATIONS",
}


@dataclass(frozen=True)
class Mention:
    raw_text: str
    section: Section
    evidence_text: str
    skill_id: str | None
    skill_name: str | None
    normalization_status: NormalizationStatus
    position: int


def safe_filename(filename: str) -> str:
    if not filename or len(filename) > 255 or PurePath(filename).name != filename:
        raise ValueError("Unsafe filename")
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", filename).strip(" .")
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError("Unsafe filename")
    return cleaned


def validate_document(
    filename: str, media_type: str, content: bytes, maximum: int
) -> tuple[str, str]:
    name = safe_filename(filename)
    if not content:
        raise ValueError("EMPTY")
    if len(content) > maximum:
        raise ValueError("TOO_LARGE")
    extension = PurePath(name).suffix.casefold()
    if extension == ".pdf" and media_type == PDF and content.startswith(b"%PDF-"):
        return name, "pdf"
    if extension == ".docx" and media_type == DOCX and content.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                entries = archive.infolist()
                names = {item.filename for item in entries}
                if (
                    len(entries) > 200
                    or "[Content_Types].xml" not in names
                    or "word/document.xml" not in names
                ):
                    raise ValueError("CORRUPT")
                expanded = sum(item.file_size for item in entries)
                compressed = max(1, sum(item.compress_size for item in entries))
                if expanded > 10_000_000 or expanded / compressed > 100:
                    raise ValueError("CORRUPT")
        except (zipfile.BadZipFile, RuntimeError) as exc:
            raise ValueError("CORRUPT") from exc
        return name, "docx"
    raise ValueError("UNSUPPORTED")


def extract_text(content: bytes, kind: str, max_pages: int, max_chars: int) -> str:
    try:
        if kind == "pdf":
            reader = PdfReader(io.BytesIO(content), strict=True)
            if len(reader.pages) > max_pages:
                raise ValueError("TOO_MANY_PAGES")
            raw = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        else:
            document = Document(io.BytesIO(content))
            raw = "\n".join(paragraph.text for paragraph in document.paragraphs)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("CORRUPT") from exc
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.replace("\r", "").split("\n")]
    text = "\n".join(line for line in lines if line)
    if len(text) < 10:
        raise ValueError("NEEDS_OCR_OR_EMPTY")
    if len(text) > max_chars:
        raise ValueError("TEXT_TOO_LARGE")
    return text


def detect_mentions(text: str, skills: list[Entity]) -> list[Mention]:
    aliases: dict[str, tuple[Entity, NormalizationStatus, str]] = {}
    for skill in skills:
        aliases[normalize_alias(skill.name)] = (skill, "EXACT", skill.name)
        for alias in skill.aliases:
            aliases[normalize_alias(alias)] = (skill, "ALIAS", alias)
    found: list[Mention] = []
    current: Section = "OTHER"
    for position, line in enumerate(text.splitlines()):
        normalized_line = normalize_alias(line.strip(" :|-"))
        if normalized_line in HEADINGS:
            current = HEADINGS[normalized_line]
            continue
        matched: set[str] = set()
        for alias, (skill, status, display) in sorted(
            aliases.items(), key=lambda item: -len(item[0])
        ):
            if skill.id in matched:
                continue
            if re.search(rf"(?<![\w+.#-]){re.escape(alias)}(?![\w+.#-])", normalize_alias(line)):
                found.append(
                    Mention(display, current, line[:500], skill.id, skill.name, status, position)
                )
                matched.add(skill.id)
        if current == "SKILLS":
            for token in re.split(r"[,;|\u2022]", line):
                candidate = token.strip(" -\t")
                key = normalize_alias(candidate)
                if not candidate or len(candidate) > 120 or len(candidate.split()) > 4:
                    continue
                if key in aliases or not re.search(r"[A-Za-z]", candidate):
                    continue
                found.append(
                    Mention(candidate, current, line[:500], None, None, "UNRESOLVED", position)
                )
    unique: dict[tuple[int, str | None, str], Mention] = {}
    for mention in found:
        unique.setdefault(
            (mention.position, mention.skill_id, normalize_alias(mention.raw_text)), mention
        )
    return list(unique.values())
