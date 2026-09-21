$server = Start-Process -FilePath "C:\Program Files\nodejs\node.exe" -ArgumentList "C:\Program Files\nodejs\node_modules\npm\bin\npx-cli.js", "vite", "preview", "--host", "127.0.0.1", "--port", "4173" -PassThru -RedirectStandardOutput "preview-out.log" -RedirectStandardError "preview-err.log"
Write-Host "Server started with PID: $($server.Id)"
Write-Host "Check http://127.0.0.1:4173/"
Write-Host "Press Enter to stop..."
Read-Host
Stop-Process -Id $server.Id