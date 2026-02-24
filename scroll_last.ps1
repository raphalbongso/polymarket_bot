Start-Sleep -Seconds 3

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;
public class W3 {
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
        if (IsWindowVisible(h)) { StringBuilder sb = new StringBuilder(256); GetWindowText(h, sb, 256); string t = sb.ToString(); if (t.Length > 0) { w.Add(h); n.Add(t); } }
        return true;
    }
    public static void Find() { w.Clear(); n.Clear(); EnumWindows(new CB(E), IntPtr.Zero); }
}
"@

[W3]::Find()
for ($i = 0; $i -lt [W3]::n.Count; $i++) {
    if ([W3]::n[$i] -like "*Polymarket Bot*" -and [W3]::n[$i] -like "*Chrome*") {
        [W3]::ShowWindow([W3]::w[$i], 9)
        [W3]::SetForegroundWindow([W3]::w[$i])
        break
    }
}
Start-Sleep -Seconds 1

[W3]::SetCursorPos(600, 700)
[W3]::mouse_event(0x0002, 0, 0, 0, 0)
[W3]::mouse_event(0x0004, 0, 0, 0, 0)
Start-Sleep -Milliseconds 200

for ($i = 0; $i -lt 15; $i++) {
    [W3]::mouse_event(0x0800, 0, 0, -120, 0)
    Start-Sleep -Milliseconds 40
}
Start-Sleep -Seconds 2

$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$bmp.Save("C:\Users\rapha\polymarket_bot\screenshot_trades_view.png")
$g.Dispose()
$bmp.Dispose()
