@echo off
REM Install dependencies without compilation issues

echo ============================================================
echo INSTALLING INTELLI-CREDIT DEPENDENCIES
echo ============================================================
echo.

echo This will install all required packages...
echo.

REM Upgrade pip first
echo [1/3] Upgrading pip...
python -m pip install --upgrade pip
echo.

REM Install core dependencies (no compilation needed)
echo [2/3] Installing core dependencies...
pip install fastapi uvicorn[standard] python-multipart pydantic pydantic-settings python-dotenv
pip install sqlalchemy aiosqlite
pip install pandas numpy openpyxl networkx
pip install httpx beautifulsoup4 feedparser lxml
pip install scikit-learn joblib openai
pip install python-dateutil aiofiles
echo.

REM Install PyMuPDF (will use pre-built wheel)
echo [3/3] Installing PyMuPDF (PDF processing)...
pip install --upgrade pymupdf
echo.

echo ============================================================
echo INSTALLATION COMPLETE!
echo ============================================================
echo.
echo Optional packages (not required for core functionality):
echo   - pytesseract (for OCR - requires Tesseract installation)
echo   - opencv-python-headless (for image preprocessing)
echo   - pdfplumber (for advanced table extraction)
echo   - xgboost (for ML - optional)
echo.
echo You can now run: start_app.bat
echo.
pause
