$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$package = Get-Content package.json -Raw | ConvertFrom-Json
$plugin = Get-Content plugin.json -Raw | ConvertFrom-Json
$version = $package.version
$zipSlug = $package.name
$pluginName = $plugin.name
$stagingDir = Join-Path "release-staging" $pluginName
$zipName = "$zipSlug-v$version.zip"

if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
    throw "pnpm is required. Install with: npm i -g pnpm@9"
}

Write-Host "Building $pluginName v$version..."
pnpm run build

if (Test-Path release-staging) { Remove-Item -Recurse -Force release-staging }
New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null

Copy-Item -Recurse dist, backend, main.py, plugin.json, package.json, LICENSE, README.md -Destination $stagingDir

Get-ChildItem (Join-Path $stagingDir "backend") -Filter "*.sh" | ForEach-Object {
    $text = [System.IO.File]::ReadAllText($_.FullName) -replace "`r`n", "`n" -replace "`r", "`n"
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($_.FullName, $text, $utf8)
}

Get-ChildItem "$zipSlug-v*.zip" -ErrorAction SilentlyContinue | Remove-Item -Force
Compress-Archive -Path (Join-Path release-staging $pluginName) -DestinationPath $zipName -Force

Write-Host "Created $zipName"
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::OpenRead((Resolve-Path $zipName)).Entries | ForEach-Object { $_.FullName }
