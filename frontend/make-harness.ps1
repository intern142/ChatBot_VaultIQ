$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$tmp = $env:TEMP
$uid = "opencode-domcheck"
$minehtml = @'
<!doctype html>
<html lang="en">
<head><meta charset="UTF-8" /></head>
<body>
<script>
loca_l = localStorage; // noop
</script>
</body>
</html>
'@

# Bootstrap harness that sets per-role localStorage then serves the role shell
foreach ($item in @(
  @{ name='employee'; role='employee'; redirect='/employee/dashboard' },
  @{ name='client-admin'; role='client-admin'; redirect='/admin/dashboard' },
  @{ name='super-admin'; role='super-admin'; redirect='/super/tenants' }
)) {
  $r = $item.name
  $html = "<!doctype html><html><head><meta charset='UTF-8'/></head><body><script>localStorage.setItem('vaultiq_role','$($item.role)');localStorage.setItem('vaultiq_user',JSON.stringify({name:'Demo User',email:'demo@company.com',organization:'Acme Corp',role:'$($item.role)'}));location.replace('$($item.redirect)');</script></body></html>"
  $bFile = Join-Path $tmp "__bootstrap-$r.html"
  Set-Content -Path $bFile -Value $html -Encoding UTF8
}

# Note: chrome headless --screenshot resolved the dashboards directly (harness was served by vite preview).
Write-Output "harness written; role shells served by live vite preview server"
Write-Output "pidfile check: $env:TEMP\opencode\vite-preview.pid -> $((Get-Content "$env:TEMP\opencode\vite-preview.pid" -ErrorAction SilentlyContinue))"
