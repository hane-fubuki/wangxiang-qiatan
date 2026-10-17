$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Install beside a Windows-user-encrypted credential.xml. Never log credentials,
# API response errors, prompts, or request headers to stdout/stderr.
function Invoke-GrokApi($Path, $Body) {
    $credential = $null
    $apiKey = $null
    try {
        $credential = Import-Clixml -LiteralPath (Join-Path $PSScriptRoot 'credential.xml')
        $apiKey = $credential.GetNetworkCredential().Password
        $params = @{
            Uri = ('https://api.x.ai/v1/' + $Path)
            Headers = @{ Authorization = ('Bearer ' + $apiKey) }
            TimeoutSec = 300
            MaximumRedirection = 0
        }
        if ($null -ne $Body) {
            $params.Method = 'Post'
            $params.ContentType = 'application/json; charset=utf-8'
            $params.Body = [Text.Encoding]::UTF8.GetBytes(($Body | ConvertTo-Json -Depth 30 -Compress))
        } else { $params.Method = 'Get' }
        # Windows PowerShell 5.1 may otherwise decode JSON without charset as
        # Latin-1. xAI responses are UTF-8; decode the response bytes explicitly.
        $response = Invoke-WebRequest @params -UseBasicParsing
        $response.RawContentStream.Position = 0
        $reader = New-Object System.IO.StreamReader($response.RawContentStream, [Text.Encoding]::UTF8)
        try { return ($reader.ReadToEnd() | ConvertFrom-Json) }
        finally { $reader.Dispose() }
    } catch {
        if ($null -ne $_.Exception.Response) {
            throw ('Grok API request failed (HTTP ' + [int]$_.Exception.Response.StatusCode + '). Check credentials, account balance, model access, or retry later.')
        }
        throw 'Grok connection unavailable. Check the local encrypted credential and network connection.'
    } finally { $apiKey = $null; $credential = $null }
}

$toolList = @(
    @{
        name = 'ask_grok'
        description = 'Ask Grok for text, analysis, coding help, or a second opinion. Sends only the supplied prompt to xAI; does not read files or automatically send conversation history. Default model: grok-4.7.'
        inputSchema = @{
            type = 'object'
            properties = @{
                prompt = @{ type = 'string'; minLength = 1; maxLength = 200000; description = 'The complete question and context to send to Grok.' }
                model = @{ type = 'string'; description = 'Optional Grok chat model ID from list_grok_models.' }
                max_output_tokens = @{ type = 'integer'; minimum = 1; maximum = 32768; description = 'Combined thinking and final answer budget, default 16384 (32768 for high) on known reasoning models.' }
                reasoning_effort = @{ type = 'string'; enum = @('medium', 'high'); description = 'Reasoning effort on Grok 4.5, 4.6, and 4.7, default medium. Unknown models use their API default.' }
            }
            required = @('prompt')
            additionalProperties = $false
        }
        annotations = @{ readOnlyHint = $true; destructiveHint = $false; openWorldHint = $true }
    },
    @{
        name = 'list_grok_models'
        description = 'List model IDs accessible using the saved xAI credential.'
        inputSchema = @{ type = 'object'; properties = @{}; additionalProperties = $false }
        annotations = @{ readOnlyHint = $true; destructiveHint = $false; openWorldHint = $true }
    }
)

while ($null -ne ($line = [Console]::ReadLine())) {
    $request = $null
    try {
        if ($line.Length -gt 1048576) { throw 'Request too large.' }
        $request = $line | ConvertFrom-Json
        if ($null -eq $request.id) { continue }
        $result = $null
        switch ($request.method) {
            'initialize' {
                $version = $request.params.protocolVersion
                if ($version -notin @('2024-11-05', '2025-03-26', '2025-06-18', '2025-11-25')) { $version = '2024-11-05' }
                $result = @{ protocolVersion = $version; capabilities = @{ tools = @{} }; serverInfo = @{ name = 'local-grok'; version = '1.1.0' } }
            }
            'ping' { $result = @{} }
            'tools/list' { $result = @{ tools = $toolList } }
            'tools/call' {
                try {
                    $arguments = $request.params.arguments
                    switch ($request.params.name) {
                        'list_grok_models' {
                            $models = Invoke-GrokApi 'models' $null
                            $text = @($models.data | Select-Object id) | ConvertTo-Json -Depth 8 -Compress
                        }
                        'ask_grok' {
                            if ($arguments.prompt -isnot [string] -or [string]::IsNullOrWhiteSpace($arguments.prompt) -or $arguments.prompt.Length -gt 200000) { throw 'prompt must be a non-empty string of at most 200000 characters.' }
                            $model = 'grok-4.7'
                            if ($null -ne $arguments.model) {
                                if ($arguments.model -isnot [string]) { throw 'Invalid Grok model ID.' }
                                $model = $arguments.model
                            }
                            if ($model.Length -gt 128 -or $model -notmatch '^grok-[a-zA-Z0-9._-]+$') { throw 'Invalid Grok model ID.' }
                            $effort = 'medium'
                            if ($null -ne $arguments.reasoning_effort) {
                                if ($arguments.reasoning_effort -isnot [string] -or $arguments.reasoning_effort -cnotin @('medium', 'high')) { throw 'reasoning_effort must be medium or high.' }
                                $effort = $arguments.reasoning_effort
                            }
                            $supportsReasoning = $model -match '^grok-4\.[567](-(?:latest|\d{8}|\d{4}-\d{2}-\d{2}))?$'
                            $maxTokens = 4096
                            if ($supportsReasoning) { $maxTokens = $(if ($effort -eq 'high') { 32768 } else { 16384 }) }
                            if ($null -ne $arguments.max_output_tokens) {
                                if ($arguments.max_output_tokens -isnot [int] -and $arguments.max_output_tokens -isnot [long]) { throw 'max_output_tokens must be an integer.' }
                                $maxTokens = [long]$arguments.max_output_tokens
                                if ($maxTokens -lt 1 -or $maxTokens -gt 32768) { throw 'max_output_tokens must be 1-32768.' }
                            }
                            $body = @{ model = $model; messages = @(@{ role = 'user'; content = $arguments.prompt }); max_tokens = $maxTokens; stream = $false }
                            if ($supportsReasoning) { $body.reasoning_effort = $effort }
                            if ($arguments.prompt.Contains('<conversation_data>') -and $arguments.prompt.Contains('"speak"')) {
                                $body.response_format = @{ type = 'json_object' }
                            }
                            $response = Invoke-GrokApi 'chat/completions' $body
                            $text = [string]$response.choices[0].message.content
                            if ($response.choices[0].finish_reason -eq 'length') { throw 'Grok output reached the token limit; shorten the request or increase the output budget.' }
                            if ([string]::IsNullOrWhiteSpace($text)) { throw 'Grok returned no text.' }
                        }
                        default { throw 'Unknown tool.' }
                    }
                    $result = @{ content = @(@{ type = 'text'; text = $text }) }
                } catch {
                    $result = @{ isError = $true; content = @(@{ type = 'text'; text = [string]$_.Exception.Message }) }
                }
            }
            default { throw 'Unknown method.' }
        }
        $reply = @{ jsonrpc = '2.0'; id = $request.id; result = $result }
    } catch {
        $reply = @{ jsonrpc = '2.0'; id = $(if ($null -ne $request) { $request.id } else { $null }); error = @{ code = -32600; message = 'Invalid MCP request.' } }
    }
    [Console]::WriteLine(($reply | ConvertTo-Json -Depth 40 -Compress))
}
