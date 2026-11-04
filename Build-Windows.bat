@echo off
setlocal
pushd "%~dp0" || exit /b 1
call gradlew.bat --no-daemon --console=plain clean build %*
set "build_exit=%errorlevel%"
if "%build_exit%"=="0" echo Built Fabric mod in "%~dp0build\libs".
popd
exit /b %build_exit%
