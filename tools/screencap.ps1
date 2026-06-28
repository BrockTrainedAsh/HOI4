# screencap.ps1 - capture a strip of the primary screen to a PNG.
# Used by the agent (via WSL->Windows interop) and by hoi4_watch.py to "see" the
# HOI4 top bar (Political Power, Manpower, Stability, the in-game date, etc.).
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File screencap.ps1 -Out C:\...\top.png -H 80
param(
    [Parameter(Mandatory = $true)][string]$Out,
    [int]$H = 80,
    [int]$Y = 0
)
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$w = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width
$bmp = New-Object System.Drawing.Bitmap($w, $H)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen(0, $Y, 0, 0, (New-Object System.Drawing.Size($w, $H)))
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output ("saved {0} ({1}x{2})" -f $Out, $w, $H)
