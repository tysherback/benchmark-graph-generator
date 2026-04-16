@echo off
echo Installing / upgrading dependencies...
pip install --upgrade numpy pandas matplotlib pyinstaller

echo.
echo Building BenchmarkGraphGenerator.exe ...
pyinstaller BenchmarkGraphGenerator.spec --clean

echo.
if exist dist\BenchmarkGraphGenerator.exe (
    echo Build succeeded: dist\BenchmarkGraphGenerator.exe
) else (
    echo Build FAILED. Check the output above for errors.
    exit /b 1
)
