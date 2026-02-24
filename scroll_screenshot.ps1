Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class ScreenHelper {
    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")]
    public static extern void mouse_event(int dwFlags, int dx, int dy, int dwData, int dwExtraInfo);
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@

# Minimize foreground window
$hw = [ScreenHelper]::GetForegroundWindow()
[ScreenHelper]::ShowWindow($hw, 6)
Start-Sleep -Milliseconds 500

# Send Alt+Tab to get to browser
[System.Windows.Forms.SendKeys]::SendWait("%{TAB}")
Start-Sleep -Seconds 1

# Click middle of screen
[ScreenHelper]::SetCursorPos(500, 500)
[ScreenHelper]::mouse_event(0x0002, 0, 0, 0, 0)
[ScreenHelper]::mouse_event(0x0004, 0, 0, 0, 0)
Start-Sleep -Milliseconds 300

# Scroll down
for ($i = 0; $i -lt 8; $i++) {
    [ScreenHelper]::mouse_event(0x0800, 0, 0, -600, 0)
    Start-Sleep -Milliseconds 150
}
Start-Sleep -Seconds 2

# Screenshot
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$bmp.Save("C:\Users\rapha\polymarket_bot\screenshot_trades7.png")
$g.Dispose()
$bmp.Dispose()
Write-Output "Done"
