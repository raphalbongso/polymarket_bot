# Wait for terminal to lose focus
Start-Sleep -Seconds 3

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;
public class WF {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("user32.dll")] public static extern bool EnumWindows(CB cb, IntPtr l);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int m);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(int f, int x, int y, int d, int e);
    public delegate bool CB(IntPtr h, IntPtr l);
    public static List<IntPtr> w = new List<IntPtr>();
    public static List<string> n = new List<string>();
    public static bool E(IntPtr h, IntPtr l) {
        if (IsWindowVisible(h)) {
            StringBuilder sb = new StringBuilder(256);
            GetWindowText(h, sb, 256);
            string t = sb.ToString();
            if (t.Length > 0) { w.Add(h); n.Add(t); }
        }
        return true;
    }
    public static void Find() { w.Clear(); n.Clear(); EnumWindows(new CB(E), IntPtr.Zero); }
}
"@

# Find and activate the dashboard Chrome window
[WF]::Find()
for ($i = 0; $i -lt [WF]::n.Count; $i++) {
    $t = [WF]::n[$i]
    if ($t -like "*Polymarket Bot*" -and $t -like "*Chrome*") {
        [WF]::ShowWindow([WF]::w[$i], 9)
        [WF]::SetForegroundWindow([WF]::w[$i])
        break
    }
}
Start-Sleep -Seconds 1

# Scroll down from current position
[WF]::SetCursorPos(600, 400)
Start-Sleep -Milliseconds 200
for ($i = 0; $i -lt 40; $i++) {
    [WF]::mouse_event(0x0800, 0, 0, -120, 0)
    Start-Sleep -Milliseconds 40
}
Start-Sleep -Seconds 2

# Screenshot
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$bmp.Save("C:\Users\rapha\polymarket_bot\screenshot_trades_final.png")
$g.Dispose()
$bmp.Dispose()
