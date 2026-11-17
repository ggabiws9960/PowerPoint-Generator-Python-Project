param([string]$Pptx, [string]$OutDir)
# Windows 전용 검사 도구: PowerPoint COM 으로 열어 슬라이드마다 PNG 를 뽑는다.
# 열리면 파일이 온전한 것이고, PNG 를 보면 겹침·넘침을 눈으로 잡을 수 있다.
#   powershell -ExecutionPolicy Bypass -File preview.ps1 -Pptx out\sample-ko.pptx -OutDir out\png
$Pptx = (Resolve-Path $Pptx).Path
if (Test-Path $OutDir) { Get-ChildItem $OutDir -Filter *.PNG | ForEach-Object { $_.Delete() } } else { New-Item -ItemType Directory $OutDir | Out-Null }
$OutDir = (Resolve-Path $OutDir).Path
$before = @(Get-Process POWERPNT -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
$app = New-Object -ComObject PowerPoint.Application
$after = @(Get-Process POWERPNT -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
$mine = $after | Where-Object { $before -notcontains $_ }
try {
  $pres = $app.Presentations.Open($Pptx, $true, $false, $false)
  Write-Output ("slides=" + $pres.Slides.Count)
  $pres.Export($OutDir, "PNG", 1600, 900)
  $pres.Close()
} finally {
  $app.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
  foreach ($id in $mine) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
}
Get-ChildItem $OutDir | Select-Object -ExpandProperty Name
