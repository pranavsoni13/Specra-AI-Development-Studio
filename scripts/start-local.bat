@echo off
setlocal
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "PYTHON="
if exist "%ROOT%\backend\.dev\Scripts\python.exe" set "PYTHON=%ROOT%\backend\.dev\Scripts\python.exe"
if not defined PYTHON if exist "%ROOT%\backend\.venv\Scripts\python.exe" set "PYTHON=%ROOT%\backend\.venv\Scripts\python.exe"
if defined PYTHON (
  start "Specra Backend" cmd /k "cd /d ""%ROOT%\backend"" && ""%PYTHON%"" -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
) else (
  start "Specra Backend" cmd /k "cd /d ""%ROOT%\backend"" && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
)
start "Specra Frontend" cmd /k "cd /d ""%ROOT%\frontend"" && npm run dev"
echo Specra backend and frontend terminal windows have been opened.
echo Ensure Ollama is running before generating artifacts.
endlocal
