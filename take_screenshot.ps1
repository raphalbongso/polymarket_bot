Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;
public class WinFinder {
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")]
    public static extern bool EnumWindows(CallBack cb, IntPtr lParam);
    [DllImport("user32.dll")]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder sb, int max);
    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
    public delegate bool CallBack(IntPtr hWnd, IntPtr lParam);
    public static List<IntPtr> windows = new List<IntPtr>();
    public static List<string> titles = new List<string>();
    public static bool EnumCallback(IntPtr hWnd, IntPtr lParam) {
        if (IsWindowVisible(hWnd)) {
            StringBuilder sb = new StringBuilder(256);
            GetWindowText(hWnd, sb, 256);
            string t = sb.ToString();
            if (t.Length > 0) { windows.Add(hWnd); titles.Add(t); }
        }
        return true;
    }
    public static void Find() {
        windows.Clear(); titles.Clear();
        EnumWindows(new CallBack(EnumCallback), IntPtr.Zero);
    }
}
"@

# Find all windows
[WinFinder]::Find()
for ($i = 0; $i -lt [WinFinder]::titles.Count; $i++) {
    $t = [WinFinder]::titles[$i]
    if ($t -like "*Polymarket Bot*" -and $t -notlike "*cmd*" -and $t -notlike "*Claude*") {
        Write-Output "Found: $t"
        $hwnd = [WinFinder]::windows[$i]
        [WinFinder]::ShowWindow($hwnd, 3)  # maximize
        [WinFinder]::SetForegroundWindow($hwnd)
        break
    }
}

Start-Sleep -Seconds 1

# Press End key to scroll to bottom
[System.Windows.Forms.SendKeys]::SendWait("{END}")
Start-Sleep -Seconds 2

# Screenshot
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$bmp.Save("C:\Users\rapha\polymarket_bot\screenshot_bottom.png")
$g.Dispose()
$bmp.Dispose()
Write-Output "Screenshot saved"
