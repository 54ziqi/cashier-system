@echo off
chcp 65001 >nul 2>&1

REM ============================================================
REM  柒号收银系统 v3.2 - 一键构建（带进度信息）
REM  调用 build.bat，方便双击执行
REM ============================================================

echo.
echo ============================================
echo   柒号收银系统 v3.2 - 一键构建
echo ============================================
echo.

REM 记录开始时间
for /f "tokens=2 delims==" %%i in ('wmic os get localdatetime /value') do set "START=%%i"
echo 开始时间: %START:~0,4%-%START:~4,2%-%START:~6,2% %START:~8,2%:%START:~10,2%:%START:~12,2%
echo.

REM 调用主构建脚本
call "%~dp0build.bat"
set "BUILD_RESULT=%ERRORLEVEL%"

REM 计算耗时
for /f "tokens=2 delims==" %%i in ('wmic os get localdatetime /value') do set "END=%%i"
echo.
echo 结束时间: %END:~0,4%-%END:~4,2%-%END:~6,2% %END:~8,2%:%END:~10,2%:%END:~12,2%

if %BUILD_RESULT% equ 0 (
    echo.
    echo ============================================
    echo   构建成功！请查看 打包\win\输出\ 目录
    echo ============================================
) else (
    echo.
    echo ============================================
    echo   构建失败，请查看上方错误信息
    echo ============================================
)

pause
exit /b %BUILD_RESULT%
