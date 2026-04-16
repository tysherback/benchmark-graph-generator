@echo off
setlocal

echo ============================================================
echo  Benchmark Graph Generator -- Build Script
echo ============================================================
echo.

echo [1/2] Installing / upgrading dependencies...
pip install --upgrade numpy pandas matplotlib pyinstaller
if errorlevel 1 (
    echo.
    echo ERROR: pip install failed. See above.
    goto :fail
)

echo.
echo [2/2] Building EXE...
pyinstaller BenchmarkGraphGenerator.spec --clean --log-level INFO > build.log 2>&1
type build.log

echo.
if exist dist\BenchmarkGraphGenerator.exe (
    echo ============================================================
    echo  SUCCESS: dist\BenchmarkGraphGenerator.exe
    echo ============================================================
    echo.
    pause
    exit /b 0
)

:fail
echo ============================================================
echo  BUILD FAILED
echo  Full log saved to: build.log
echo  Common causes:
echo    - Run this .bat from inside the repo folder
echo    - Check Python is 3.12+  (run: python --version)
echo    - Read build.log for the exact error
echo ============================================================
echo.
pause
exit /b 1
