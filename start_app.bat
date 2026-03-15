@echo off
REM Intelli-Credit Application Launcher
REM Starts both backend and frontend servers

echo ============================================================
echo INTELLI-CREDIT APPLICATION LAUNCHER
echo ============================================================
echo.

REM Check if we're in the correct directory
if not exist "backend" (
    echo ERROR: backend folder not found!
    echo Please run this script from the project root directory.
    pause
    exit /b 1
)

if not exist "frontend" (
    echo ERROR: frontend folder not found!
    echo Please run this script from the project root directory.
    pause
    exit /b 1
)

echo [1/4] Checking Python...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found! Please install Python 3.11+
    pause
    exit /b 1
)
echo     Python found!

echo.
echo [2/4] Checking Node.js...
node --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Node.js not found! Please install Node.js
    pause
    exit /b 1
)
echo     Node.js found!

echo.
echo [3/4] Starting Backend Server...
echo     Backend will run on: http://localhost:8000
echo     API Docs will be at: http://localhost:8000/api/docs
echo.

REM Start backend in a new window
start "Intelli-Credit Backend" cmd /k "cd backend && uvicorn main:app --reload --port 8000"

REM Wait a bit for backend to start
timeout /t 3 /nobreak >nul

echo [4/4] Starting Frontend Server...
echo     Frontend will run on: http://localhost:5173
echo.

REM Start frontend in a new window
start "Intelli-Credit Frontend" cmd /k "cd frontend && npm run dev"

REM Wait a bit for frontend to start
timeout /t 5 /nobreak >nul

echo.
echo ============================================================
echo APPLICATION STARTED SUCCESSFULLY!
echo ============================================================
echo.
echo Two new windows have opened:
echo   1. Backend Server  (http://localhost:8000)
echo   2. Frontend Server (http://localhost:5173)
echo.
echo Opening browser in 3 seconds...
timeout /t 3 /nobreak >nul

REM Open browser
start http://localhost:5173

echo.
echo ============================================================
echo QUICK LINKS:
echo ============================================================
echo   Dashboard:  http://localhost:5173
echo   API Docs:   http://localhost:8000/api/docs
echo   ReDoc:      http://localhost:8000/api/redoc
echo.
echo To stop the servers:
echo   - Close the Backend and Frontend terminal windows
echo   - Or press CTRL+C in each window
echo.
echo ============================================================
echo Press any key to close this window...
pause >nul
