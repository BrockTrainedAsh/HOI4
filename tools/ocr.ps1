# ocr.ps1 - OCR a PNG with the built-in Windows OCR engine (no pip, no install).
# Optionally crop to a region first (for reading just one number off the HOI4 bar).
#   powershell -NoProfile -ExecutionPolicy Bypass -File ocr.ps1 -Path C:\...\top.png
#   powershell ... -File ocr.ps1 -Path C:\...\top.png -X 200 -Y 0 -W 140 -H 90
param(
    [Parameter(Mandatory = $true)][string]$Path,
    [int]$X = -1, [int]$Y = 0, [int]$W = 0, [int]$H = 0, [int]$Scale = 3
)

# Optional crop to a sub-region, UPSCALED $Scale x (small HUD digits OCR poorly at
# native size - 6/5/8/9 get confused; enlarging with smooth interpolation fixes it).
$ocrPath = $Path
if ($X -ge 0 -and $W -gt 0 -and $H -gt 0) {
    Add-Type -AssemblyName System.Drawing
    $src = [System.Drawing.Image]::FromFile($Path)
    $sw = $W * $Scale; $sh = $H * $Scale
    $crop = New-Object System.Drawing.Bitmap($sw, $sh)
    $g = [System.Drawing.Graphics]::FromImage($crop)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $g.DrawImage($src, (New-Object System.Drawing.Rectangle(0, 0, $sw, $sh)),
                 (New-Object System.Drawing.Rectangle($X, $Y, $W, $H)),
                 [System.Drawing.GraphicsUnit]::Pixel)
    $ocrPath = [System.IO.Path]::ChangeExtension($Path, $null) + "crop.png"
    $crop.Save($ocrPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $crop.Dispose(); $src.Dispose()
}

# WinRT OCR (synchronous await helper for Windows PowerShell 5.1)
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Foundation, ContentType = WindowsRuntime]
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
                   $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, $type) {
    $t = $asTask.MakeGenericMethod($type).Invoke($null, @($op))
    $t.Wait(); $t.Result
}

$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ocrPath)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) { Write-Output "OCR_ENGINE_NULL"; exit 1 }
$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
Write-Output $result.Text
