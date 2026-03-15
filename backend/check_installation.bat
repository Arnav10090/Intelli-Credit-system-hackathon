@echo off
REM Quick installation check script

echo ============================================================
echo CHECKING INSTALLATION
echo ============================================================
echo.

echo [1/10] Checking Python...
python --version
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)
echo.

echo [2/10] Checking FastAPI...
python -c "import fastapi; print('  FastAPI:', fastapi.__version__)"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: FastAPI not installed!
    echo Run: pip install fastapi
    pause
    exit /b 1
)

echo [3/10] Checking Uvicorn...
python -c "import uvicorn; print('  Uvicorn: OK')"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Uvicorn not installed!
    pause
    exit /b 1
)

echo [4/10] Checking Pydantic...
python -c "import pydantic; print('  Pydantic:', pydantic.__version__)"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Pydantic not installed!
    pause
    exit /b 1
)

echo [5/10] Checking SQLAlchemy...
python -c "import sqlalchemy; print('  SQLAlchemy:', sqlalchemy.__version__)"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: SQLAlchemy not installed!
    pause
    exit /b 1
)

echo [6/10] Checking aiosqlite...
python -c "import aiosqlite; print('  aiosqlite: OK')"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: aiosqlite not installed!
    echo Run: pip install aiosqlite
    pause
    exit /b 1
)

echo [7/10] Checking PyMuPDF...
python -c "import fitz; print('  PyMuPDF:', fitz.version)"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PyMuPDF not installed!
    echo Run: pip install --upgrade pymupdf
    pause
    exit /b 1
)

echo [8/10] Checking pandas...
python -c "import pandas; print('  pandas:', pandas.__version__)"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: pandas not installed!
    pause
    exit /b 1
)

echo [9/10] Checking scikit-learn...
python -c "import sklearn; print('  scikit-learn:', sklearn.__version__)"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: scikit-learn not installed!
    pause
    exit /b 1
)

echo [10/10] Checking custom modules...
python -c "from ingestor.document_classifier import classify_document; print('  Document Classifier: OK')"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Custom modules not loading!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo ALL CHECKS PASSED!
echo ============================================================
echo.
echo Your installation is complete and working!
echo.
echo Next steps:
echo   1. Go back to project root: cd ..
echo   2. Run: start_app.bat
echo   3. Open browser: http://localhost:5173
echo.
echo ============================================================
pause
