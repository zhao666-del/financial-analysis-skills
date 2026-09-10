param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$upstream = Join-Path $root "references\external-data\upstream"
New-Item -ItemType Directory -Force -Path $upstream | Out-Null

$sources = @(
    @{
        Name = "a-stock-data"
        Commit = "9ed665cc9773457bc23fed6b770b2b5a8cede40f"
        SkillSha = "a1cd1220f7ea1c57bb508dba78f1bfe9d9f92bed7a5e1f32f43afea41543c3de"
        LicenseSha = "199bab40163ad21135c2c4d5db43bffdadb14ed80762b048f04931cc48700bbf"
        Repo = "simonlin1212/a-stock-data"
    },
    @{
        Name = "global-stock-data"
        Commit = "d52a8a0013363577bceb28ca876c88fe6c1a5aeb"
        SkillSha = "39005851f179f74d970caccfb775bcffb9dd64d2ccedacca5c611fc4ebf101a8"
        LicenseSha = "199bab40163ad21135c2c4d5db43bffdadb14ed80762b048f04931cc48700bbf"
        Repo = "simonlin1212/global-stock-data"
    }
)

function Save-PinnedFile {
    param(
        [string[]]$Urls,
        [string]$Destination,
        [string]$ExpectedSha
    )

    foreach ($url in $Urls) {
        $temp = [System.IO.Path]::GetTempFileName()
        try {
            & curl.exe -L --fail --silent --show-error `
                --retry 3 --retry-delay 2 --retry-all-errors `
                --connect-timeout 20 --max-time 180 `
                -o $temp $url
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "Download route failed: $url"
                continue
            }
            $actual = (Get-FileHash -LiteralPath $temp -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($actual -ne $ExpectedSha) {
                throw "SHA-256 mismatch for $url`: $actual"
            }
            Move-Item -LiteralPath $temp -Destination $Destination -Force
            return
        }
        finally {
            if (Test-Path -LiteralPath $temp) {
                Remove-Item -LiteralPath $temp -Force
            }
        }
    }

    throw "All download routes failed for $Destination"
}

foreach ($source in $sources) {
    $cdn = "https://cdn.jsdelivr.net/gh/$($source.Repo)@$($source.Commit)"
    $base = "https://raw.githubusercontent.com/$($source.Repo)/$($source.Commit)"
    Save-PinnedFile `
        -Urls @("$cdn/SKILL.md", "$base/SKILL.md") `
        -Destination (Join-Path $upstream "$($source.Name).SKILL.md") `
        -ExpectedSha $source.SkillSha
    Save-PinnedFile `
        -Urls @("$cdn/LICENSE", "$base/LICENSE") `
        -Destination (Join-Path $upstream "$($source.Name).LICENSE") `
        -ExpectedSha $source.LicenseSha

    $integrationRef = Join-Path $root "integrations\skills\$($source.Name)\references"
    New-Item -ItemType Directory -Force -Path $integrationRef | Out-Null
    Copy-Item `
        -LiteralPath (Join-Path $upstream "$($source.Name).SKILL.md") `
        -Destination (Join-Path $integrationRef "upstream.md") `
        -Force
    Copy-Item `
        -LiteralPath (Join-Path $upstream "$($source.Name).LICENSE") `
        -Destination (Join-Path $integrationRef "LICENSE") `
        -Force
}

Write-Output "Pinned external data skills synchronized."
