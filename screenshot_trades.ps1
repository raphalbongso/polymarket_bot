Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;
public class WF3 {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
    [DllImport("user32.dll")] public static extern bool EnumWindows(CB cb, IntPtr l);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int m);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, uint d, UIntPtr e);
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

[WF3]::Go()
for ($i = 0; $i -lt [WF3]::names.Count; $i++) {
    $t = [WF3]::names[$i]
    if ($t -like "*Polymarket Bot*" -and $t -notlike "*cmd*" -and $t -notlike "*Claude*") {
        Write-Output "Found: $t"
        $hwnd = [WF3]::wins[$i]
        [WF3]::ShowWindow($hwnd, 3)
        [WF3]::SetForegroundWindow($hwnd)
        break
    }
}

Start-Sleep -Seconds 1
[System.Windows.Forms.SendKeys]::SendWait("{HOME}")
Start-Sleep -Milliseconds 500

# Click Trades tab (right side of header bar)
[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point(1380, 62)
Start-Sleep -Milliseconds 200
[WF3]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
[WF3]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
Start-Sleep -Seconds 2

$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$bmp.Save("C:\Users\rapha\polymarket_bot\screenshot_trades_tab.png")
$g.Dispose()
$bmp.Dispose()
Write-Output "Screenshot saved"
