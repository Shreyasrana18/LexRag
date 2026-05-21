import fitz
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, cast


class MetadataExtractionError(Exception):
    pass


@dataclass
class _TextBlock:
    text: str
    font_sizes: List[float] = field(default_factory=list)
    is_bold: bool = False

    @property
    def upper(self) -> str:
        return self.text.upper()


_NOISE = re.compile(
    r"^\d+$|^signature\s+not\s+verified|^digitally\s+signed|^date\s*:|^reason\s*:",
    re.I,
)

_CASE_NO = re.compile(
    r"((?:CIVIL|CRIMINAL|WRIT|SPECIAL LEAVE|TRANSFER|REVIEW|CURATIVE)"
    r"[\w\s/&()]+?NO[S]?\.[\s]*[\w/,\s]+(?:OF|of)\s+\d{4})",
    re.I,
)
_CASE_NO_FALLBACK = re.compile(
    r"([A-Z][\w\s/&()]+?NO[S]?\.[\s]*[\w/,\s]+(?:OF|of)\s+\d{4})", re.I
)

_COURT = re.compile(
    r"^(?:IN\s+THE\s+|BEFORE\s+THE\s+|(?:SUPREME|HIGH|DISTRICT|SESSIONS)\s+).+COURT",
    re.I,
)

_JURISDICTION_KW = {"APPELLATE", "ORIGINAL", "REVISIONAL", "WRIT", "JURISDICTION"}

_ROLE_LABEL = re.compile(
    r"(?:\.{2,3}\s*|^)(?:APPELLANT|RESPONDENT|PETITIONER|DEFENDANT|PLAINTIFF|ACCUSED)[S]?\s*$",
    re.I,
)
_INLINE_ROLE = re.compile(
    r"\.{2,3}\s*(?:APPELLANT|RESPONDENT|PETITIONER|DEFENDANT|PLAINTIFF|ACCUSED)[S]?",
    re.I,
)
_STRIP_ROLE = re.compile(
    r"\s*\.{2,3}\s*(?:APPELLANT|RESPONDENT|PETITIONER|DEFENDANT|PLAINTIFF|ACCUSED)[S]?\s*$",
    re.I,
)

_VERSUS = re.compile(r"^\s*(?:VERSUS|VS\.?)\s*$", re.I)


def parseBlocks(raw_blocks: List[Dict[str, Any]]) -> List[_TextBlock]:
    result: List[_TextBlock] = []
    for block in raw_blocks:
        if block.get("type") != 0:
            continue
        parts, font_sizes, bold_count, span_count = [], [], 0, 0
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if t := span.get("text", "").strip():
                    parts.append(t)
                font_sizes.append(span.get("size", 0.0))
                bold_count += bool(span.get("flags", 0) & 2**4)
                span_count += 1
        text = re.sub(r"\s{2,}", " ", " ".join(parts).strip())
        if text and not _NOISE.match(text):
            result.append(_TextBlock(text, font_sizes, bold_count >= max(span_count // 2, 1)))
    return result


def extractCase(blocks: List[_TextBlock]) -> Optional[str]:
    candidates = blocks + [
        _TextBlock(blocks[i].text + " " + blocks[i + 1].text)
        for i in range(len(blocks) - 1)
    ]
    for block in candidates:
        m = _CASE_NO.search(block.text) or _CASE_NO_FALLBACK.search(block.text)
        if m:
            return m.group(1).strip()
    return None


def extractCourt(blocks: List[_TextBlock]) -> Optional[str]:
    court_lines: List[str] = []
    for block in blocks:
        if _COURT.match(block.upper):
            court_lines.append(block.text)
        elif court_lines:
            if _CASE_NO.search(block.upper) or _ROLE_LABEL.search(block.text) or _VERSUS.match(block.text):
                break
            if set(block.upper.split()) & _JURISDICTION_KW:
                court_lines.append(block.text)
            else:
                break
    return " | ".join(court_lines) or None


def extractParties(blocks: List[_TextBlock]) -> tuple[Optional[str], Optional[str]]:
    def is_boundary(b: _TextBlock) -> bool:
        return bool(_CASE_NO.search(b.upper) or _COURT.match(b.upper) or re.match(r"^[A-Z\s]+JURISDICTION$", b.upper))

    try:
        vi = next(i for i, b in enumerate(blocks) if _VERSUS.match(b.text))
    except StopIteration:
        return None, None

    pet_parts: List[str] = []
    for block in reversed(blocks[:vi]):
        if _ROLE_LABEL.search(block.text) and not _INLINE_ROLE.search(block.text):
            continue
        if is_boundary(block):
            break
        pet_parts.insert(0, _STRIP_ROLE.sub("", block.text).strip())
        if _INLINE_ROLE.search(block.text):
            break

    res_parts: List[str] = []
    for block in blocks[vi + 1:]:
        if _ROLE_LABEL.search(block.text) and not _INLINE_ROLE.search(block.text):
            if res_parts:
                break
            continue
        if _VERSUS.match(block.text) or len(block.text) < 5:
            continue
        res_parts.append(_STRIP_ROLE.sub("", block.text).strip())
        if _INLINE_ROLE.search(block.text):
            break

    return " ".join(pet_parts).strip() or None, " ".join(res_parts).strip() or None


def extractData(raw_blocks: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    blocks = parseBlocks(raw_blocks)
    court = extractCourt(blocks)
    case_number = extractCase(blocks)
    petitioners, respondents = extractParties(blocks)
    title = f"{petitioners} vs {respondents}" if petitioners and respondents else None

    required: Dict[str, Optional[str]] = {
        "title": title,
        "court": court,
        "case_number": case_number,
        "petitioners": petitioners,
        "respondents": respondents,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise MetadataExtractionError(f"Could not extract required metadata fields: {', '.join(missing)}")

    return {**required, "decision_date": None, "citation": None}


def extractParagraphs(pdf_bytes: bytes) -> List[str]:
    paragraphs: List[str] = []

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page_index in range(len(doc)):
            page = doc[page_index]
            page_dict: Dict[str, Any] = page.get_text("dict")  # type: ignore[assignment]
            raw_blocks = cast(List[Dict[str, Any]], page_dict["blocks"])

            for block in raw_blocks:
                if block.get("type") != 0:
                    continue
                parts: List[str] = [
                    span.get("text", "")
                    for line in block.get("lines", [])
                    for span in line.get("spans", [])
                ]
                cleaned = " ".join(" ".join(parts).split()).strip()
                if not cleaned:
                    continue
                if len(cleaned) < 30:
                    continue
                paragraphs.append(cleaned)

    return paragraphs


def extractMetaData(pdf_bytes: bytes) -> Dict[str, Any]:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if len(doc) == 0:
            raise MetadataExtractionError("Empty PDF.")

        page = doc[0]
        page_dict = cast(Dict[str, Any], page.get_text("dict"))
        raw_blocks = cast(List[Dict[str, Any]], page_dict["blocks"])

        metadata = extractData(raw_blocks)

    return {"metadata": metadata}