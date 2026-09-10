param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d{6}$')]
    [string]$Symbol,

    [ValidateSet('brief', 'summary', 'json', 'html', 'full')]
    [string]$Mode = 'summary'
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$Cli = Join-Path $ProjectRoot 'core\cli.py'

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python environment not found: $Python"
}

$Arguments = @($Cli, 'analyze', $Symbol)
switch ($Mode) {
    'brief'   { $Arguments += '--brief' }
    'summary' { $Arguments += '--summary' }
    'json'    { $Arguments += '--json' }
    'html'    { $Arguments += '--html' }
}

& $Python @Arguments
exit $LASTEXITCODE
