$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $ScriptDir

try {
    if ($args.Count -gt 0 -and ($args[0] -eq '-d' -or $args[0] -eq '--down')) {
        docker compose down
        exit
    }

    docker compose up -d --build

    # Wait for VPN container to be running
    Write-Host "Waiting for VPN to connect..."
    for ($i = 0; $i -lt 10; $i++) {
        $state = docker compose ps vpn --format "{{.State}}" 2>$null
        if ($state -eq "running") { break }
        Start-Sleep -Seconds 2
    }

    # Show VPN status
    docker compose logs --tail 5 vpn

    if ($args.Count -gt 0 -and ($args[0] -eq '-b' -or $args[0] -eq '--bash')) {
        docker compose exec kali bash
    } else {
        docker compose exec kali claude --dangerously-skip-permissions @args
    }
} finally {
    Pop-Location
}
