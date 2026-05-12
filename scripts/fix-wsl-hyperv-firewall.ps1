param(
    [string]$VmCreatorId = "{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}"
)

$ErrorActionPreference = "Stop"

Write-Host "Configuring Windows and Hyper-V firewall rules for WSL mirrored networking..."

Set-NetFirewallProfile -Profile Domain,Private,Public -Enabled True

Set-NetFirewallHyperVVMSetting `
    -Name $VmCreatorId `
    -DefaultInboundAction Allow `
    -DefaultOutboundAction Allow

$rules = @(
    @{
        Name = "WSL-HyperV-Allow-In"
        DisplayName = "WSL HyperV Allow In"
        Direction = "Inbound"
    },
    @{
        Name = "WSL-HyperV-Allow-Out"
        DisplayName = "WSL HyperV Allow Out"
        Direction = "Outbound"
    }
)

foreach ($rule in $rules) {
    $existing = Get-NetFirewallHyperVRule -PolicyStore ActiveStore -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq $rule.Name }

    if (-not $existing) {
        New-NetFirewallHyperVRule `
            -Name $rule.Name `
            -DisplayName $rule.DisplayName `
            -Direction $rule.Direction `
            -VMCreatorId $VmCreatorId `
            -Protocol Any `
            -Action Allow | Out-Null
    }
}

Write-Host ""
Write-Host "Current Hyper-V firewall setting:"
Get-NetFirewallHyperVVMSetting -Name $VmCreatorId |
    Format-List Name,Enabled,DefaultInboundAction,DefaultOutboundAction

Write-Host "WSL Hyper-V firewall rules:"
Get-NetFirewallHyperVRule -PolicyStore ActiveStore |
    Where-Object { $_.Name -like "WSL-HyperV-Allow-*" } |
    Format-Table -AutoSize Name,Direction,Action,Protocol,Enabled,VMCreatorId

Write-Host ""
Write-Host "Done. Run 'wsl --shutdown', reopen Ubuntu, then restart the project with 'docker compose up -d'."
