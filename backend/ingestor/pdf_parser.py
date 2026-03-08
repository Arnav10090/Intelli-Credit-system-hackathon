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

from config import settings

# Company name detection patterns (Requirements 2.2)
# Patterns ordered to match most specific to least specific
# Note: Using [ \t] instead of \s to avoid matching newlines
COMPANY_PATTERNS = [
    # Pattern for "Pvt. Ltd." or "Pvt Ltd" (common in India)
    r'([A-Z][A-Za-z]+(?:[ \t]+[A-Z&][A-Za-z]*)*[ \t]+Pvt\.[ \t]*Ltd\.)',
    # Pattern for "Private Limited" (mixed case)
    r'([A-Z][A-Za-z]+(?:[ \t]+[A-Z&][A-Za-z]*)*[ \t]+Private[ \t]+Limited)\b',
    # Pattern for all-caps legal suffixes
    r'([A-Z][A-Za-z]+(?:[ \t]+[A-Z&][A-Za-z]*)*[ \t]+(?:LIMITED|LTD|PVT|PRIVATE|COMPANY|CORPORATION))\b',
    # Pattern for mixed-case legal suffixes (excluding Private Limited which is handled above)
    r'([A-Z][A-Za-z]+(?:[ \t]+[A-Z&][A-Za-z]*)*[ \t]+(?:Limited|Ltd|Company|Corporation))\b',
    # Pattern for "Pvt." or "Ltd." with period
    r'([A-Z][A-Za-z]+(?:[ \t]+[A-Z&][A-Za-z]*)*[ \t]+(?:Pvt|Ltd)\.)',
]

# Currency pattern for financial figure extraction (Requirements 3.1, 3.2, 3.5)
# Matches currency indicators (₹, Rs., Rs, INR) followed by numeric values
# Supports Indian number formats with Crore, Cr, Lakh, Lac suffixes
CURRENCY_PATTERN = r'(?:₹|Rs\.?|INR)\s*[\d,]+(?:\.\d+)?(?:\s*(?:Crore|Cr|Lakh|Lac))?'

# Key sections for document section detection (Requirements 4.2)
# Standard financial document sections to detect
KEY_SECTIONS = [
    "Directors Report",
    "Director's Report",
    "Balance Sheet",
    "Profit and Loss",
    "P&L Statement",
    "Cash Flow",
    "Notes to Accounts",
    "Auditors Report",
    "Auditor's Report",
    "Independent Auditor"
]

# Risk keywords for risk phrase detection (Requirements 5.2)
# Case-insensitive matching will be applied during detection
RISK_KEYWORDS = [
    "litigation",
    "NCLT",
    "NPA",
    "non-performing",
    "default",
    "winding up",
    "insolvency",
    "bankruptcy",
    "dishonour",
    "dishonored",
    "penalty",
    "show cause",
    "regulatory action",
    "fraud"
]


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

    # Extract page texts for risk phrase detection
    page_texts = [p.text for p in pages]
    
    risk_phrases = _detect_risk_phrases(page_texts)
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


def _extract_text_with_pymupdf(pdf_document) -> tuple[list[str], list[int]]:
    """
    Extract text from all pages using PyMuPDF (fitz).
    
    Args:
        pdf_document: An opened fitz.Document object
        
    Returns:
        Tuple of (page_texts: list[str], char_counts: list[int])
        - page_texts: List of extracted text strings, one per page
        - char_counts: List of character counts, one per page
        
    Raises:
        Exception: If PyMuPDF encounters errors during text extraction
    """
    page_texts = []
    char_counts = []
    
    try:
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            text = page.get_text("text")
            page_texts.append(text)
            char_counts.append(len(text))
    except Exception as e:
        logger.error("PyMuPDF text extraction failed: %s", e)
        raise
    
    return page_texts, char_counts


def _calculate_confidence(char_counts: list[int]) -> float:
    """
    Calculate confidence score based on character counts per page.

    Args:
        char_counts: List of character counts, one per page

    Returns:
        Float between 0.0 and 1.0 representing the ratio of pages
        with more than 100 characters to total pages

    Requirements: 1.5
    """
    if not char_counts:
        return 0.0

    pages_with_content = sum(1 for count in char_counts if count > 100)
    confidence_score = pages_with_content / len(char_counts)

    return confidence_score


def _apply_ocr_fallback(pdf_document, low_confidence_pages: list[int]) -> list[str]:
    """
    Apply OCR fallback to pages with low confidence extraction.
    
    Args:
        pdf_document: An opened fitz.Document object
        low_confidence_pages: List of 0-indexed page numbers that need OCR
        
    Returns:
        List of OCR-extracted text strings, one per low_confidence_page.
        Returns empty strings for pages that fail OCR or if pytesseract is unavailable.
        
    Requirements: 1.3, 1.6, 12.2, 12.4
    
    Notes:
        - Limits OCR processing to first 3 pages maximum for performance
        - Handles missing pytesseract gracefully by returning empty strings
        - Uses 300 DPI for OCR quality
    """
    ocr_texts = []
    
    # Check if pytesseract is available
    if not TESSERACT_AVAILABLE:
        logger.warning("pytesseract not available. Returning empty strings for OCR fallback.")
        return [""] * len(low_confidence_pages)
    
    # Limit to first 3 pages for performance (Requirement 12.2, 12.4)
    pages_to_process = low_confidence_pages[:3]
    
    for page_idx in pages_to_process:
        try:
            # Get the page object
            page = pdf_document[page_idx]
            
            # Render page to image at 300 DPI
            mat = fitz.Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))
            
            # Apply OpenCV preprocessing if available
            if CV2_AVAILABLE:
                img = _preprocess_image_cv2(img)
            
            # Run Tesseract OCR
            text = pytesseract.image_to_string(
                img,
                lang=settings.OCR_LANG,
                config="--psm 6"
            )
            
            ocr_texts.append(text.strip())
            logger.info(f"OCR completed for page {page_idx + 1}: {len(text)} characters extracted")
            
        except Exception as e:
            logger.error(f"OCR failed on page {page_idx + 1}: {e}")
            ocr_texts.append("")
    
    # If we had more than 3 pages but only processed 3, fill the rest with empty strings
    remaining_pages = len(low_confidence_pages) - len(pages_to_process)
    if remaining_pages > 0:
        ocr_texts.extend([""] * remaining_pages)
        logger.info(f"Skipped OCR for {remaining_pages} pages beyond the first 3")
    
    return ocr_texts


def _apply_ocr_fallback(pdf_document, low_confidence_pages: list[int]) -> list[str]:
    """
    Apply OCR fallback to pages with low confidence extraction.

    Args:
        pdf_document: An opened fitz.Document object
        low_confidence_pages: List of 0-indexed page numbers that need OCR

    Returns:
        List of OCR-extracted text strings, one per low_confidence_page.
        Returns empty strings for pages that fail OCR or if pytesseract is unavailable.

    Requirements: 1.3, 1.6, 12.2, 12.4

    Notes:
        - Limits OCR processing to first 3 pages maximum for performance
        - Handles missing pytesseract gracefully by returning empty strings
        - Uses 300 DPI for OCR quality
    """
    ocr_texts = []

    # Check if pytesseract is available
    if not TESSERACT_AVAILABLE:
        logger.warning("pytesseract not available. Returning empty strings for OCR fallback.")
        return [""] * len(low_confidence_pages)

    # Limit to first 3 pages for performance (Requirement 12.2, 12.4)
    pages_to_process = low_confidence_pages[:3]

    for page_idx in pages_to_process:
        try:
            # Get the page object
            page = pdf_document[page_idx]

            # Render page to image at 300 DPI
            mat = fitz.Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))

            # Apply OpenCV preprocessing if available
            if CV2_AVAILABLE:
                img = _preprocess_image_cv2(img)

            # Run Tesseract OCR
            text = pytesseract.image_to_string(
                img,
                lang=settings.OCR_LANG,
                config="--psm 6"
            )

            ocr_texts.append(text.strip())
            logger.info(f"OCR completed for page {page_idx + 1}: {len(text)} characters extracted")

        except Exception as e:
            logger.error(f"OCR failed on page {page_idx + 1}: {e}")
            ocr_texts.append("")

    # If we had more than 3 pages but only processed 3, fill the rest with empty strings
    remaining_pages = len(low_confidence_pages) - len(pages_to_process)
    if remaining_pages > 0:
        ocr_texts.extend([""] * remaining_pages)
        logger.info(f"Skipped OCR for {remaining_pages} pages beyond the first 3")

    return ocr_texts




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


def _detect_company_name(page_texts: list[str]) -> str | None:
    """
    Detect company name from the first 5 pages.
    
    **Validates: Requirements 2.1, 2.3, 2.4, 2.5**
    
    Searches for company name patterns containing legal suffixes like
    LIMITED, LTD, PVT, PRIVATE, COMPANY, or CORPORATION.
    
    Args:
        page_texts: List of text strings, one per page
        
    Returns:
        Full company name with legal suffixes, or None if no match found
    """
    # Search only first 5 pages (Requirement 2.1)
    pages_to_search = page_texts[:5]
    
    # Prioritize earlier pages by searching in order (Requirement 2.3)
    for page_text in pages_to_search:
        for pattern in COMPANY_PATTERNS:
            match = re.search(pattern, page_text)
            if match:
                # Return full company name including legal suffixes (Requirement 2.5)
                return match.group(1).strip()
    
    # Return None if no pattern matches (Requirement 2.4)
    return None


def _detect_key_sections(full_text: str) -> list[str]:
    """
    Detect key document sections by matching against predefined list.
    
    **Validates: Requirements 4.1, 4.3, 4.4, 4.5**
    
    Performs case-insensitive matching for standard financial document sections.
    Handles whitespace variations and line breaks. Returns deduplicated list.
    
    Args:
        full_text: Complete extracted text from the PDF
        
    Returns:
        List of detected section names (deduplicated)
    """
    detected_sections = []
    seen = set()
    
    # Normalize the full text for matching: collapse whitespace and line breaks
    # This handles sections split across lines or with extra whitespace (Requirement 4.5)
    normalized_text = re.sub(r'\s+', ' ', full_text)
    
    # Perform case-insensitive matching against KEY_SECTIONS (Requirement 4.3)
    for section in KEY_SECTIONS:
        # Normalize the section name for matching
        normalized_section = re.sub(r'\s+', ' ', section)
        
        # Create a regex pattern that allows flexible whitespace
        # This handles variations in whitespace and line breaks
        pattern = re.escape(normalized_section).replace(r'\ ', r'\s+')
        
        # Search case-insensitively
        if re.search(pattern, normalized_text, re.IGNORECASE):
            # Use lowercase for deduplication check (Requirement 4.4)
            section_lower = section.lower()
            if section_lower not in seen:
                seen.add(section_lower)
                detected_sections.append(section)
    
    return detected_sections


def _detect_risk_phrases(page_texts: list[str]) -> list[dict]:
    """
    Scan for risk keywords with page numbers.
    
    **Validates: Requirements 5.1, 5.3, 5.4, 5.5**
    
    Scans all page texts for risk keywords from RISK_KEYWORDS list.
    Performs case-insensitive matching and tracks page numbers.
    Returns deduplicated list of dicts with 'phrase' and 'page' fields.
    
    Args:
        page_texts: List of text strings, one per page
        
    Returns:
        List of dicts with 'phrase' (str) and 'page' (int, 1-indexed)
    """
    detected_phrases = []
    seen = set()
    
    # Scan each page for risk keywords (Requirement 5.1)
    for page_num, page_text in enumerate(page_texts, start=1):
        page_text_lower = page_text.lower()
        
        # Check each risk keyword (Requirement 5.2)
        for keyword in RISK_KEYWORDS:
            keyword_lower = keyword.lower()
            
            # Case-insensitive matching (Requirement 5.3)
            if keyword_lower in page_text_lower:
                # Deduplicate: only add if not already seen (Requirement 5.4)
                if keyword_lower not in seen:
                    seen.add(keyword_lower)
                    detected_phrases.append({
                        'phrase': keyword,  # Use original keyword casing
                        'page': page_num    # 1-indexed page number (Requirement 5.5)
                    })
    
    return detected_phrases


def _generate_text_preview(full_text: str, max_chars: int = 2000) -> str:
    """
    Generate a preview of the extracted text.
    
    **Validates: Requirements 6.1, 6.3, 6.4, 6.5**
    
    Extracts the first max_chars characters from the full text,
    preserving line breaks and basic formatting. Truncates at word
    boundaries when possible to avoid cutting words.
    
    Args:
        full_text: Complete extracted text from the PDF
        max_chars: Maximum number of characters to include (default: 2000)
        
    Returns:
        Text preview string, truncated to max_chars or less
    """
    # If text is shorter than max_chars, return all of it (Requirement 6.4)
    if len(full_text) <= max_chars:
        return full_text
    
    # Extract first max_chars characters (Requirement 6.1)
    preview = full_text[:max_chars]
    
    # Try to truncate at word boundary (Requirement 6.5)
    # Find the last space within the preview
    last_space = preview.rfind(' ')
    
    # If we found a space and it's reasonably close to the end (within 50 chars),
    # truncate there to avoid cutting a word
    if last_space > max_chars - 50:
        preview = preview[:last_space]
    
    # Line breaks and basic formatting are preserved automatically (Requirement 6.3)
    return preview



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
    Extract all financial figures with currency indicators from text.
    Returns a dict with 'figures' (list of dicts with 'value' and 'context')
    and 'count' (total number of figures found).
    
    Requirements: 3.1, 3.3, 3.4
    """
    figures_list = []
    
    # Find all matches of currency patterns in the text
    for match in re.finditer(CURRENCY_PATTERN, full_text, re.IGNORECASE):
        value = match.group(0)
        start_pos = match.start()
        end_pos = match.end()
        
        # Extract context: 20 characters before and after
        context_start = max(0, start_pos - 20)
        context_end = min(len(full_text), end_pos + 20)
        context = full_text[context_start:context_end].strip()
        
        figures_list.append({
            'value': value,
            'context': context
        })
    
    return {
        'figures': figures_list,
        'count': len(figures_list)
    }


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



def extract_from_pdf(file_bytes: bytes, filename: str) -> dict:
    """
    Main orchestrator function for PDF text extraction and structured data extraction.

    This function coordinates all helper functions to extract text from a PDF and
    identify structured entities like company names, financial figures, sections,
    and risk phrases.

    **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**

    Args:
        file_bytes: Raw bytes of the PDF file
        filename: Original filename for logging/debugging

    Returns:
        Dictionary containing:
        - page_count: int - Number of pages in the PDF
        - extraction_method: str - "digital", "ocr", or "ocr_unavailable"
        - confidence_score: float - 0.0 to 1.0 ratio of high-quality pages
        - company_name: str | None - Detected company name or None
        - financial_figures: list[dict] - List of dicts with 'value' and 'context'
        - key_sections: list[str] - List of detected section names
        - risk_phrases: list[dict] - List of dicts with 'phrase' and 'page'
        - raw_text_preview: str - First 2000 characters of extracted text

    Raises:
        Exception: If PyMuPDF is not available or PDF cannot be opened
    """
    # Check if PyMuPDF is available (Requirement 10.1)
    if not PYMUPDF_AVAILABLE:
        logger.error("PyMuPDF library not available")
        raise Exception("PyMuPDF library not available")

    try:
        # Open PDF with PyMuPDF (Requirement 10.2)
        pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        logger.error(f"Failed to open PDF {filename}: {e}")
        raise Exception(f"Unable to process PDF file: {str(e)}")

    try:
        # Extract text from all pages using PyMuPDF (Requirement 1.2, 10.2)
        page_texts, char_counts = _extract_text_with_pymupdf(pdf_document)

        # Calculate confidence score (Requirement 1.5, 10.2)
        confidence_score = _calculate_confidence(char_counts)

        # Determine if OCR fallback is needed (Requirement 1.3, 10.2)
        # Pages with < 100 characters need OCR
        low_confidence_pages = [i for i, count in enumerate(char_counts) if count < 100]

        extraction_method = "digital"

        # Apply OCR fallback if needed (Requirement 1.3, 10.2)
        if low_confidence_pages:
            # Check if pytesseract is available (Requirement 1.6, 10.3)
            if not TESSERACT_AVAILABLE:
                extraction_method = "ocr_unavailable"
                logger.warning(f"OCR needed for {len(low_confidence_pages)} pages but pytesseract unavailable")
            else:
                # Apply OCR to low confidence pages (first 3 max)
                ocr_texts = _apply_ocr_fallback(pdf_document, low_confidence_pages)

                # Merge OCR results back into page_texts
                for i, page_idx in enumerate(low_confidence_pages[:3]):
                    if i < len(ocr_texts) and ocr_texts[i]:
                        page_texts[page_idx] = ocr_texts[i]
                        char_counts[page_idx] = len(ocr_texts[i])

                extraction_method = "ocr"

                # Recalculate confidence after OCR
                confidence_score = _calculate_confidence(char_counts)

        # Combine all page texts into full text
        full_text = "\n\n".join(page_texts)

        # Call all pattern matcher functions (Requirement 10.2)
        company_name = _detect_company_name(page_texts)
        financial_figures_result = _extract_financial_figures(full_text)
        key_sections = _detect_key_sections(full_text)
        risk_phrases = _detect_risk_phrases(page_texts)

        # Generate raw text preview (Requirement 10.2)
        raw_text_preview = _generate_text_preview(full_text, max_chars=2000)

        # Assemble and return result dictionary (Requirement 1.4, 10.2)
        result = {
            "page_count": len(page_texts),
            "extraction_method": extraction_method,
            "confidence_score": confidence_score,
            "company_name": company_name,
            "financial_figures": financial_figures_result['figures'],
            "key_sections": key_sections,
            "risk_phrases": risk_phrases,
            "raw_text_preview": raw_text_preview
        }

        logger.info(
            f"PDF extraction complete: {filename} | pages={result['page_count']} | "
            f"method={extraction_method} | confidence={confidence_score:.2f} | "
            f"company={company_name} | figures={len(financial_figures_result['figures'])} | "
            f"sections={len(key_sections)} | risks={len(risk_phrases)}"
        )

        return result

    finally:
        # Always close the PDF document
        pdf_document.close()

