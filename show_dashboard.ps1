Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;
public class Finder {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("user32.dll")] public static extern bool EnumWindows(CB cb, IntPtr l);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int m);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    public delegate bool CB(IntPtr h, IntPtr l);
    public static List<IntPtr> wins = new List<IntPtr>();
    public static List<string> names = new List<string>();
    public static bool Enum(IntPtr h, IntPtr l) {
        if (IsWindowVisible(h)) {
            StringBuilder sb = new StringBuilder(256);
            GetWindowText(h, sb, 256);
            string t = sb.ToString();
            if (t.Length > 0) { wins.Add(h); names.Add(t); }
        }
        return true;
    }
    public static void Go() { wins.Clear(); names.Clear(); EnumWindows(new CB(Enum), IntPtr.Zero); }
}
"@

[Finder]::Go()

# List all windows for debugging
for ($i = 0; $i -lt [Finder]::names.Count; $i++) {
    $t = [Finder]::names[$i]
    if ($t -like "*Chrome*" -or $t -like "*Polymarket*" -or $t -like "*localhost*" -or $t -like "*Bot*") {
        Write-Output "Window: $t"
    }
}

# Find the Chrome window that has "Polymarket Bot" in title (dashboard tabs)
# There are two Chrome windows - bot's Chrome and user's Chrome
# The user's Chrome has multiple tabs including "Polymarket Bot" (dashboard)
# Try to find the one that is NOT the bot's Selenium Chrome
$found = $false
for ($i = 0; $i -lt [Finder]::names.Count; $i++) {
    $t = [Finder]::names[$i]
    # The dashboard tab title is "Polymarket Bot" served by localhost:8050
    if ($t -like "*Polymarket Bot*" -and $t -like "*Chrome*") {
        Write-Output "Activating: $t"
        $hwnd = [Finder]::wins[$i]
        [Finder]::ShowWindow($hwnd, 9)  # SW_RESTORE
        Start-Sleep -Milliseconds 200
        [Finder]::SetForegroundWindow($hwnd)
        $found = $true
        break
    }
}

if (-not $found) {
    Write-Output "Dashboard window not found, opening..."
    Start-Process "http://localhost:8050"
    Start-Sleep -Seconds 3
}

Start-Sleep -Seconds 1

# Press Ctrl+End to scroll to very bottom
[System.Windows.Forms.SendKeys]::SendWait("^{END}")
Start-Sleep -Seconds 2

# Screenshot
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$bmp.Save("C:\Users\rapha\polymarket_bot\screenshot_final.png")
$g.Dispose()
$bmp.Dispose()
Write-Output "Screenshot saved"
