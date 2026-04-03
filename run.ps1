$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$entrypoint = @()
$passArgs = $args

if ($args.Count -gt 0 -and ($args[0] -eq '-b' -or $args[0] -eq '--bash')) {
    $entrypoint = @('--entrypoint', 'bash')
    $passArgs = $args[1..($args.Count - 1)]
}

docker run -it --rm `
    --cap-add=NET_ADMIN `
    --device=/dev/net/tun `
    -e TERM=xterm-256color `
    --env-file "$ScriptDir/.env" `
    -v "${ScriptDir}:/htb" `
    -v "ptb-home:/home/hacker" `
    @entrypoint `
    ptb @passArgs
