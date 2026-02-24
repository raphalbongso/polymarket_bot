Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class S {
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(int f, int x, int y, int d, int e);
}
"@

[S]::SetCursorPos(600, 400)
Start-Sleep -Milliseconds 200

for ($i = 0; $i -lt 30; $i++) {
    [S]::mouse_event(0x0800, 0, 0, -120, 0)
    Start-Sleep -Milliseconds 50
}
Start-Sleep -Seconds 2

$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$bmp.Save("C:\Users\rapha\polymarket_bot\screenshot_more.png")
$g.Dispose()
$bmp.Dispose()
Write-Output "Done"
