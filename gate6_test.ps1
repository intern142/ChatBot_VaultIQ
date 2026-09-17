Write-Host "=== VQ-103 GATE 6 ==="
Write-Host ""

Write-Host "TEST 1: Health check"
$h = Invoke-RestMethod -Uri "http://localhost:8000/health"
Write-Host "GET /health → $($h.status)"
Write-Host ""

Write-Host "TEST 2: Tenant A login"
$body2 = '{"organisation_code":"TENANT_A","email":"usera@tenant_a.com","password":"StrongPass1!"}'
$la = Invoke-RestMethod -Uri "http://localhost:8000/auth/login" -Method POST -ContentType "application/json" -Body $body2
Write-Host "tenant_id: $($la.tenant_id)"
Write-Host "role: $($la.role)"
Write-Host ""

Write-Host "TEST 3: Tampered token"
$tampered = $la.access_token.Substring(0, $la.access_token.Length - 10) + "TAMPEREDXX"
try { Invoke-RestMethod -Uri "http://localhost:8000/auth/refresh" -Method POST -Headers @{Authorization="Bearer $tampered"} } catch { Write-Host "Status: $($_.Exception.Response.StatusCode.value__)" }
Write-Host ""

Write-Host "TEST 4: Suspended tenant"
$body4 = '{"organisation_code":"SUSPENDED","email":"user@suspended.com","password":"StrongPass1!"}'
try { Invoke-RestMethod -Uri "http://localhost:8000/auth/login" -Method POST -ContentType "application/json" -Body $body4 } catch { Write-Host "Status: $($_.Exception.Response.StatusCode.value__)" }
Write-Host ""

Write-Host "TEST 5: Super admin login"
$body5 = '{"organisation_code":"SUPER","email":"super@admin.com","password":"AdminPass1!"}'
$sa = Invoke-RestMethod -Uri "http://localhost:8000/auth/login" -Method POST -ContentType "application/json" -Body $body5
Write-Host "tenant_id: $($sa.tenant_id)"
Write-Host "role: $($sa.role)"
