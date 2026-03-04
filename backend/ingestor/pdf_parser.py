"""
ingestor/pdf_parser.py
─────────────────────────────────────────────────────────────────────────────
PDF ingestion pipeline for Intelli-Credit.

Strategy (layered):
  Layer 1 — PyMuPDF (fitz): Extract embedded text from digital PDFs instantly.
             If a page has > 50 chars of embedded text → skip OCR.
  Layer 2 — Tesseract OCR: For scanned pages, preprocess with OpenCV
             (deskew, denoise, binarize) then OCR.
  Layer 3 — Structure recovery: Detect section headers, table regions.
  Layer 4 — Risk phrase detection: Run litigation lexicon over full text.
  Layer 5 — Confidence scoring: Flag pages with OCR confidence < threshold.

LLM is NOT used here. All extraction is deterministic.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.warning("PyMuPDF not installed.")

try:
    import pytesseract
    from PIL import Image
    import io
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract/Pillow not installed. OCR disabled.")

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from config import settings, LEXICON_PATH


@dataclass
class PageResult:
    page_num: int
    text: str
    method: str
    confidence: float
    word_count: int
    has_table_hint: bool
    warnings: list = field(default_factory=list)


@dataclass
class PDFExtractionResult:
    doc_id: str
    filename: str
    page_count: int
    pages: list
    full_text: str
    avg_confidence: float
    low_confidence_pages: list
    risk_phrases_found: list
    section_headers: list
    extraction_warnings: list
    financial_figures: dict
    doc_type_detected: str


async def extract_pdf(doc_id: str, file_path: str) -> PDFExtractionResult:
    """Main entry point. Extracts text and structured data from a PDF."""
    path = Path(file_path)
    logger.info("Starting PDF extraction: %s (doc_id=%s)", path.name, doc_id)

    if not PYMUPDF_AVAILABLE:
        return _fallback_extraction(doc_id, path)

    try:
        doc = fitz.open(str(path))
    except Exception as e:
        logger.error("Failed to open PDF %s: %s", file_path, e)
        return _empty_result(doc_id, path.name, str(e))

    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_result = _process_page(page, page_num)
        pages.append(page_result)
    doc.close()

    full_text = "\n\n".join(p.text for p in pages if p.text.strip())

    ocr_pages = [p for p in pages if p.method == "ocr"]
    avg_conf = (sum(p.confidence for p in ocr_pages) / len(ocr_pages)
                if ocr_pages else 100.0)

    low_conf_pages = [p.page_num for p in pages
                      if p.confidence < settings.OCR_CONFIDENCE_THRESHOLD]

    risk_phrases = _detect_risk_phrases(full_text, pages)
    section_hdrs = _extract_section_headers(full_text)
    fin_figures  = _extract_financial_figures(full_text)
    doc_type     = _detect_document_type(full_text, path.name)
    warnings     = _collect_warnings(pages, low_conf_pages)

    result = PDFExtractionResult(
        doc_id=doc_id,
        filename=path.name,
        page_count=len(pages),
        pages=pages,
        full_text=full_text,
        avg_confidence=round(avg_conf, 1),
        low_confidence_pages=low_conf_pages,
        risk_phrases_found=risk_phrases,
        section_headers=section_hdrs,
        extraction_warnings=warnings,
        financial_figures=fin_figures,
        doc_type_detected=doc_type,
    )

    logger.info(
        "PDF extracted: %s | pages=%d | avg_conf=%.1f%% | risk_phrases=%d | figures=%d",
        path.name, len(pages), avg_conf, len(risk_phrases), len(fin_figures)
    )
    return result


def _process_page(page, page_num: int) -> PageResult:
    """Process a single page: digital first, OCR fallback."""
    digital_text = page.get_text("text").strip()
    if len(digital_text) > 50:
        return PageResult(
            page_num=page_num + 1, text=digital_text, method="digital",
            confidence=100.0, word_count=len(digital_text.split()),
            has_table_hint=_has_table_hint(digital_text),
        )
    if not TESSERACT_AVAILABLE:
        return PageResult(
            page_num=page_num + 1, text=digital_text, method="empty",
            confidence=0.0, word_count=0, has_table_hint=False,
            warnings=["Tesseract not available; scanned page skipped"],
        )
    return _ocr_page(page, page_num)


def _ocr_page(page, page_num: int) -> PageResult:
    """Render page to image and run Tesseract OCR."""
    warnings = []
    try:
        mat = fitz.Matrix(300 / 72, 300 / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))

        if CV2_AVAILABLE:
            img = _preprocess_image_cv2(img)

        ocr_data = pytesseract.image_to_data(
            img, lang=settings.OCR_LANG,
            output_type=pytesseract.Output.DICT,
            config="--psm 6",
        )

        words, confidences = [], []
        for i, word in enumerate(ocr_data["text"]):
            conf = int(ocr_data["conf"][i])
            if conf > 0 and word.strip():
                words.append(word)
                confidences.append(conf)

        text = " ".join(words)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        if avg_conf < settings.OCR_CONFIDENCE_THRESHOLD:
            warnings.append(
                f"Page {page_num+1}: Low OCR confidence ({avg_conf:.1f}%)."
            )

        return PageResult(
            page_num=page_num + 1, text=text, method="ocr",
            confidence=round(avg_conf, 1), word_count=len(words),
            has_table_hint=_has_table_hint(text), warnings=warnings,
        )
    except Exception as e:
        logger.error("OCR failed on page %d: %s", page_num + 1, e)
        return PageResult(
            page_num=page_num + 1, text="", method="ocr",
            confidence=0.0, word_count=0, has_table_hint=False,
            warnings=[f"OCR error: {str(e)}"],
        )


def _preprocess_image_cv2(img):
    """OpenCV preprocessing: grayscale → denoise → binarize → deskew."""
    from PIL import Image as PILImage
    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    _, binary = cv2.threshold(denoised, 0, 255,
                               cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    binary = _deskew(binary)
    return PILImage.fromarray(binary)


def _deskew(image):
    """Simple deskew using minAreaRect."""
    try:
        coords = np.column_stack(np.where(image < 128))
        if len(coords) == 0:
            return image
        angle = cv2.minAreaRect(coords)[-1]
        angle = -(90 + angle) if angle < -45 else -angle
        if abs(angle) < 0.5:
            return image
        h, w = image.shape
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        return cv2.warpAffine(image, M, (w, h),
                              flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)
    except Exception:
        return image


def _detect_risk_phrases(full_text: str, pages: list) -> list:
    """Scan for litigation/risk phrases from the lexicon."""
    try:
        with open(LEXICON_PATH) as f:
            lexicon = json.load(f)
    except Exception as e:
        logger.error("Failed to load lexicon: %s", e)
        return []

    found = []
    seen = set()
    page_texts = {p.page_num: p.text for p in pages}
    tier_order = {"tier_1": 0, "tier_2": 1, "tier_3": 2, "positive_signals": 3}

    for tier_key in ("tier_1", "tier_2", "tier_3", "positive_signals"):
        tier_data = lexicon.get(tier_key, {})
        score_delta = tier_data.get("score_delta", 0)
        label = tier_data.get("label", tier_key)

        for phrase in tier_data.get("phrases", []):
            phrase_lower = phrase.lower()
            if phrase_lower in seen:
                continue

            matches = list(re.finditer(
                re.escape(phrase_lower), full_text.lower()
            ))
            if not matches:
                continue

            match = matches[0]
            start = max(0, match.start() - 100)
            end   = min(len(full_text), match.end() + 100)
            context = full_text[start:end].replace("\n", " ").strip()

            # Negation check
            ctx_before = context.lower()[:100]
            if any(neg in ctx_before for neg in
                   ["no ", "not ", "never ", "without ", "nil "]):
                continue

            page_num = _find_page_for_text(phrase, page_texts)
            seen.add(phrase_lower)
            found.append({
                "phrase": phrase,
                "tier": tier_key,
                "tier_label": label,
                "score_delta": score_delta,
                "page_num": page_num,
                "context": context,
                "occurrence_count": len(matches),
            })

    found.sort(key=lambda x: tier_order.get(x["tier"], 9))
    logger.info("Risk phrase detection: %d phrases found", len(found))
    return found


def _extract_section_headers(full_text: str) -> list:
    """Detect ALL-CAPS section headers in financial documents."""
    known_sections = [
        "DIRECTOR", "MANAGEMENT DISCUSSION", "AUDITOR", "BALANCE SHEET",
        "PROFIT AND LOSS", "CASH FLOW", "NOTES TO ACCOUNTS", "RELATED PARTY",
        "SHAREHOLDING PATTERN", "CORPORATE GOVERNANCE", "KEY MANAGERIAL",
        "SIGNIFICANT ACCOUNTING", "CONTINGENT LIABILITIES",
    ]
    headers, seen = [], set()
    for i, line in enumerate(full_text.split("\n")):
        ls = line.strip()
        if not ls or len(ls) < 4:
            continue
        is_header = (
            (ls == ls.upper() and 4 <= len(ls) <= 80
             and sum(c.isalpha() for c in ls) > 3)
            or any(sec in ls.upper() for sec in known_sections)
        )
        if is_header and ls not in seen:
            seen.add(ls)
            headers.append({"text": ls, "line_num": i + 1})
    return headers[:50]


def _extract_financial_figures(full_text: str) -> dict:
    """
    Extract key financial figures using regex.
    DETERMINISTIC — no LLM. Conservative patterns to avoid false positives.
    """
    figures = {}
    text = re.sub(r"\s+", " ", full_text)

    patterns = {
        "revenue": [
            r"(?:revenue from operations|net revenue|turnover)[^\d]{0,30}([\d,]+(?:\.\d+)?)",
        ],
        "ebitda": [
            r"(?:EBITDA|earnings before interest)[^\d]{0,30}([\d,]+(?:\.\d+)?)",
        ],
        "pat": [
            r"(?:profit after tax|PAT|profit for the year)[^\d]{0,30}([\d,]+(?:\.\d+)?)",
        ],
        "total_debt": [
            r"(?:total borrowings|total debt)[^\d]{0,30}([\d,]+(?:\.\d+)?)",
        ],
        "net_worth": [
            r"(?:net worth|shareholders.{0,5}equity)[^\d]{0,30}([\d,]+(?:\.\d+)?)",
        ],
        "total_assets": [
            r"(?:total assets)[^\d]{0,20}([\d,]+(?:\.\d+)?)",
        ],
        "dscr_stated": [
            r"(?:DSCR|debt service coverage)[^\d]{0,20}([\d]+\.[\d]+)",
        ],
        "loan_amount_sanctioned": [
            r"(?:sanctioned|sanction amount|loan amount)[^\d]{0,30}"
            r"(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d+)?)",
        ],
        "interest_rate_stated": [
            r"(?:interest rate|rate of interest|ROI)[^\d]{0,20}([\d]+\.?[\d]*)\s*%",
        ],
    }

    for field_name, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw = match.group(1).replace(",", "")
                try:
                    figures[field_name] = float(raw)
                    break
                except ValueError:
                    continue

    return figures


def _detect_document_type(full_text: str, filename: str) -> str:
    """Classify document type from content and filename."""
    text_upper = full_text[:3000].upper()
    name_lower = filename.lower()

    if any(k in text_upper for k in ["ANNUAL REPORT", "DIRECTORS REPORT"]):
        return "annual_report"
    if any(k in text_upper for k in ["BALANCE SHEET", "PROFIT AND LOSS"]):
        return "balance_sheet"
    if any(k in text_upper for k in ["LEGAL NOTICE", "NCLT", "SECTION 138"]):
        return "legal_notice"
    if any(k in text_upper for k in ["SANCTION LETTER", "SANCTIONED AMOUNT"]):
        return "sanction_letter"
    if any(k in text_upper for k in ["RATING RATIONALE", "CARE RATINGS", "ICRA"]):
        return "rating_report"
    if any(k in text_upper for k in ["BOARD MEETING", "MINUTES OF MEETING"]):
        return "board_minutes"
    if "annual" in name_lower:
        return "annual_report"
    if "sanction" in name_lower:
        return "sanction_letter"
    return "other"


def _has_table_hint(text: str) -> bool:
    lines_with_nums = sum(
        1 for line in text.split("\n")
        if len(re.findall(r"\d+[,\d]*\.?\d*", line)) >= 3
    )
    return lines_with_nums >= 2


def _find_page_for_text(phrase: str, page_texts: dict) -> Optional[int]:
    for page_num, text in page_texts.items():
        if phrase.lower() in text.lower():
            return page_num
    return None


def _collect_warnings(pages: list, low_conf_pages: list) -> list:
    warnings = []
    for p in pages:
        warnings.extend(p.warnings)
    if low_conf_pages:
        warnings.append(
            f"Low OCR confidence on pages: {low_conf_pages}. Manual review recommended."
        )
    return warnings


def _fallback_extraction(doc_id: str, path: Path) -> PDFExtractionResult:
    return PDFExtractionResult(
        doc_id=doc_id, filename=path.name, page_count=0, pages=[],
        full_text="", avg_confidence=0.0, low_confidence_pages=[],
        risk_phrases_found=[], section_headers=[],
        extraction_warnings=["PyMuPDF not installed"],
        financial_figures={}, doc_type_detected="other",
    )


def _empty_result(doc_id: str, filename: str, error: str) -> PDFExtractionResult:
    return PDFExtractionResult(
        doc_id=doc_id, filename=filename, page_count=0, pages=[],
        full_text="", avg_confidence=0.0, low_confidence_pages=[],
        risk_phrases_found=[], section_headers=[],
        extraction_warnings=[error],
        financial_figures={}, doc_type_detected="other",
    )


def result_to_dict(result: PDFExtractionResult) -> dict:
    return {
        "doc_id": result.doc_id,
        "filename": result.filename,
        "page_count": result.page_count,
        "avg_confidence": result.avg_confidence,
        "low_confidence_pages": result.low_confidence_pages,
        "doc_type_detected": result.doc_type_detected,
        "section_headers": result.section_headers,
        "financial_figures": result.financial_figures,
        "risk_phrases_found": result.risk_phrases_found,
        "extraction_warnings": result.extraction_warnings,
        "pages_summary": [
            {"page_num": p.page_num, "method": p.method,
             "confidence": p.confidence, "word_count": p.word_count,
             "has_table_hint": p.has_table_hint}
            for p in result.pages
        ],
    }