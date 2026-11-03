$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
    throw 'Java 21 must be installed and available on PATH.'
}
$javaVersion = & java --version | Select-Object -First 1
Write-Host "Using $javaVersion"

$version = '9.6.1'
$distDir = Join-Path $PSScriptRoot '.gradle-local'
$gradle = Join-Path $distDir "gradle-$version/bin/gradle.bat"
$zip = Join-Path $distDir "gradle-$version-bin.zip"

if (-not (Test-Path $gradle)) {
    New-Item -ItemType Directory -Force -Path $distDir | Out-Null
    $url = "https://services.gradle.org/distributions/gradle-$version-bin.zip"
    Write-Host "Downloading Gradle $version from $url"
    Invoke-WebRequest -Uri $url -OutFile $zip
    Expand-Archive -LiteralPath $zip -DestinationPath $distDir -Force
}

& $gradle --no-daemon clean build
if ($LASTEXITCODE -ne 0) { throw "Gradle build failed with exit code $LASTEXITCODE" }

$targetJar = Join-Path $PSScriptRoot 'third-person-readable-maps.jar'
$sourceJar = Join-Path $PSScriptRoot 'build/libs/third-person-readable-maps.jar'
if (-not (Test-Path $sourceJar)) { throw 'Expected remapped JAR not found.' }
Copy-Item $sourceJar $targetJar -Force
Write-Host "Built Fabric mod: $targetJar"
Write-Host 'Copy the JAR into .minecraft/mods (Fabric 1.21.11).'
