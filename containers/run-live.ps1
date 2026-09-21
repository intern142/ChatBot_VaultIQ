$ErrorActionPreference = 'Stop'
$fd = 'C:\Users\test user 2\ChatBot_VaultIQ\frontend'
Set-Location $fd

# 1) boot-harness pages (same-origin localStorage seed + redirect into the SPA)
$boot = @{
  'login'        = @{ u = $null                                        ; dest = '/login' }
  'employee'     = @{ u = '{"name":"Demo Employee","role":"employee","organization":"Acme Corp","email":"emp@acme.com"}'        ; dest = '/employee/dashboard' }
  'client-admin' = @{ u = '{"name":"Demo Client Admin","role":"client-admin","organization":"Acme Corp","email":"admin@acme.com"}' ; dest = '/admin/dashboard' }
  'super-admin'  = @{ u = '{"name":"Demo Super Admin","role":"super-admin","organization":"VaultIQ Platform","email":"super@vaultiq.com"}' ; dest = '/super/tenants' }
}
foreach ($k in $boot.Keys) {
  $b = $boot[$k]
  $seed = if ($b.u) { "localStorage.setItem('vaultiq_user', JSON.stringify($b.u));" } else { "localStorage.removeItem('vaultiq_user');" }
  $h = "<!doctype html><html><head><meta charset='utf-8'><title>boot-$k</title></head><body><script>$seed location.replace('$($b.dest)');</script></body></html>"
  Set-Content -Path "dist\__boot-$k.html" -Value $h -Encoding UTF8
}
Write-Output ("boot harness in dist: " + ((Get-ChildItem dist\__boot-*.html).Count) + " pages")

# 2) build image (context = repo root so frontend/ paths resolve)
docker build -f Dockerfile -t vaultiq-frontend:2.0.0 .. 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Error "docker build failed ($LASTEXITCODE)" }

# 3) run live container
docker rm -f vaultiq-frontend 2>&1 | Out-Null
docker run -d --name vaultiq-frontend -p 8080:80 vaultiq-frontend:2.0.0 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Error "docker run failed" }

# 4) wait until it serves
$ok = $false
for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Seconds 2
  try { $r = Invoke-WebRequest 'http://localhost:8080/login' -UseBasicParsing -TimeoutSec 3; if ($r.StatusCode -eq 200) { $ok = $true; break } } catch {}
}
Write-Output "container_serving=$ok"
docker ps --filter "name=vaultiq-frontend" --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}"
docker inspect vaultiq-frontend --format "{{.State.Status}} healthy={{.State.Health.Status}}" 2>&1
