@echo off
REM Intelli-Credit Application Stopper
REM Stops both backend and frontend servers

echo ============================================================
echo INTELLI-CREDIT APPLICATION STOPPER
echo ============================================================
echo.

echo Stopping servers...
echo.

REM Kill processes running on port 8000 (Backend)
echo [1/2] Stopping Backend Server (port 8000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo     Backend stopped successfully!
    )
)

REM Kill processes running on port 5173 (Frontend)
echo [2/2] Stopping Frontend Server (port 5173)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo     Frontend stopped successfully!
    )
)

echo.
echo ============================================================
echo SERVERS STOPPED
echo ============================================================
echo.
echo You can now restart the application using start_app.bat
echo.
pause
