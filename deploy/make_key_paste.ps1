# Run on YOUR PC, where the demo bot's keys already are:
#
#     powershell -ExecutionPolicy Bypass -File deploy\make_key_paste.ps1
#
# It reads BITGET_API_KEY / BITGET_SECRET / BITGET_PASSWORD from this PC's environment,
# builds the Azure Run command script that writes them to /etc/forexbot.env on the VM
# (root only, chmod 600), and COPIES it to the clipboard. Nothing is printed and nothing is
# written to disk. Paste the clipboard into Run command > RunShellScript, run it, and paste
# it nowhere else - it contains the keys.
#
# The values travel base64-encoded in 30-character pieces: every line stays under 44
# characters (Run command wraps long lines and runs the tail), and a password with $ # & or
# spaces in it cannot be misread by the shell.
$names = 'BITGET_API_KEY', 'BITGET_SECRET', 'BITGET_PASSWORD'
$out = @('set -e', 'F=/etc/forexbot.env', 'umask 077', ': >$F')
foreach ($n in $names) {
    $v = [Environment]::GetEnvironmentVariable($n, 'Process')
    if (-not $v) { $v = [Environment]::GetEnvironmentVariable($n, 'User') }
    if (-not $v) { $v = [Environment]::GetEnvironmentVariable($n, 'Machine') }
    if (-not $v) {
        Write-Host "$n is not set on this PC. Set it the way the demo bot gets it, then re-run."
        exit 1
    }
    # systemd reads /etc/forexbot.env with its own quoting rules, so these would reach the bot
    # changed and fail as a confusing login error. Refuse here, where the reason is clear.
    if ($v -match '["''\\$`\s]') {
        Write-Host "$n contains a quote, backslash, dollar, backtick or space, which the VM's"
        Write-Host "service file cannot carry safely. Use letters and digits on Bitget, then re-run."
        exit 1
    }
    $b = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($v))
    $out += 'V='
    for ($i = 0; $i -lt $b.Length; $i += 30) {
        $out += 'V=${V}' + $b.Substring($i, [Math]::Min(30, $b.Length - $i))
    }
    $out += "printf $n= >>`$F"
    $out += 'echo $V|base64 -d >>$F'
    $out += 'echo >>$F'
}
$out += 'V='
$out += 'chown root:root $F'
$out += 'chmod 600 $F'
$out += 'grep -c BITGET_ $F'
$out += 'echo above-must-be-3-keys-written'
($out -join "`n") | Set-Clipboard
Write-Host "Copied $($out.Count) lines to the clipboard."
Write-Host "Paste into Azure portal > VM > Run command > RunShellScript, and run."
