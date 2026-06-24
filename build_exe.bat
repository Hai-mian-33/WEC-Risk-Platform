@echo off
chcp 65001 >nul
REM ============================================================
REM  WEC-Risk Platform 一键打包脚本 / one-click build
REM  产物 / output: dist\WEC_Platform\WEC_Platform.exe
REM ============================================================
echo [1/4] 检查依赖 / install deps ...
python -m pip install -r requirements.txt

echo [2/4] 清理旧构建 / clean ...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/4] PyInstaller 打包 / build ...
pyinstaller wec_platform.spec --noconfirm --clean

echo [4/4] 复制示例数据到 exe 同级 / bundle example data next to exe ...
if exist dist\WEC_Platform (
    xcopy /e /i /y data     dist\WEC_Platform\data     >nul
    xcopy /e /i /y examples dist\WEC_Platform\examples >nul
)

echo.
echo 完成 / Done: dist\WEC_Platform\WEC_Platform.exe
echo （示例数据已置于 exe 同级 data\Miyun，"载入密云示例"可直接使用）
pause
