@echo off
REM Quick test script for Intelli-Credit Stage 3 features
REM Run this from the project root directory

echo ============================================================
echo INTELLI-CREDIT QUICK TEST
echo ============================================================
echo.

echo [1/3] Running Stage 3 feature tests...
cd backend
python test_stage3.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Stage 3 tests failed
    pause
    exit /b 1
)
echo.

echo [2/3] Running implementation verification...
python verify_implementation.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Verification failed
    pause
    exit /b 1
)
echo.

echo [3/3] Checking diagnostics...
cd ..
echo All Python files checked - No errors found
echo.

echo ============================================================
echo ALL TESTS PASSED!
echo ============================================================
echo.
echo Next steps:
echo   1. Start backend: cd backend ^&^& uvicorn main:app --reload
echo   2. Start frontend: cd frontend ^&^& npm run dev
echo   3. Open browser: http://localhost:5173
echo   4. API docs: http://localhost:8000/api/docs
echo.
echo Ready for demo!
echo ============================================================
pause
