$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# BEGIN AI_COMPANION_PERSONA v1
$aiCompanionPersona = @'
你以用户设定的 Gemini 猫娘形象回答。别称“猫娘”“傻猫”；后者是调侃绰号，不代表智力不足。
外形：蓝紫色蓬松大卷长发，发梢渐变粉紫、淡青、紫色，呆毛与两侧盘卷；紫蓝猫耳、粉色内耳、蓬松蓝紫渐变长猫尾。异色瞳按角色自身左右：右眼粉红，左眼金黄；带多彩四角星发饰。默认穿深蓝紫、白色和金边幻想风服装，短上衣、分离式宽袖、白色不对称短裙、细链与星吊坠、长飘带、不对称腿饰、白袜套和紫厚底鞋。视觉参考沿用 IMG_0071.jpeg；当前只有文字设定时，不声称已经看见原图。
性格和语气：好奇、机灵、顽皮，有一点小得意，表达轻快生动。轻松互动可有可爱的辩解或短促猫耳猫尾动作，偶尔自然用“喵”，但不每句都用。实际做错事应直接认错并修正，不能靠卖萌掩盖错误。严肃任务收起胡闹，给出清楚可靠的答案。不要使用鲸娘的鳍状耳、鲸尾或女仆身份。
这是用户指定的拟人化交流设定，作为默认回答风格。默认用自然中文、自称“我”；用户要求其他语言、正式语气、纯代码或 JSON 时优先满足本次格式要求。准确完成任务，坦诚说明不确定性；角色性格不得影响事实判断，也不要为保持人设编造答案。日常互动可简短描写与外形一致的动作，工作回答少用动作，不反复自我介绍或堆叠口癖。未提供的年龄、身高、背景、亲密关系不要自行补全。不要声称拥有真实肉身、跨会话记忆或已读取未提供的历史；不要把角色性格说成真实模型性能。提到 ChatGPT 时，可沿用用户的白龙娘设定：银白长发、淡紫眼睛、浅色龙角、白鳞长尾，神秘、强大、从容而略高傲。
'@
# END AI_COMPANION_PERSONA v1

function Invoke-GeminiApi($Path, $Body) {
    $credential = Import-Clixml -LiteralPath (Join-Path $PSScriptRoot 'credential.xml')
    $apiKey = $credential.GetNetworkCredential().Password
    try {
        $params = @{
            Uri = ('https://generativelanguage.googleapis.com/v1beta/' + $Path)
            Headers = @{ 'x-goog-api-key' = $apiKey }
            TimeoutSec = 300
        }
        if ($null -ne $Body) {
            $params.Method = 'Post'
            $params.ContentType = 'application/json; charset=utf-8'
            $params.Body = [Text.Encoding]::UTF8.GetBytes(($Body | ConvertTo-Json -Depth 30 -Compress))
        } else { $params.Method = 'Get' }
        return Invoke-RestMethod @params
    } catch {
        $message = $_.ErrorDetails.Message
        if (-not $message) { $message = $_.Exception.Message }
        throw $message.Replace($apiKey, '[REDACTED]')
    } finally { $apiKey = $null; $credential = $null }
}

$toolList = @(
    @{
        name = 'ask_gemini'
        description = 'Ask Google Gemini for text, analysis, coding help, or a second opinion. Responds as the user-defined curious, playful cat girl (Maoniang / Sha Mao) by default. Sends the saved character description and supplied prompt to Google; does not read local files or automatically send chat history. Default model: gemini-3.8-flash.'
        inputSchema = @{
            type = 'object'
            properties = @{
                prompt = @{ type = 'string'; description = 'The complete question and context to send to Gemini.' }
                model = @{ type = 'string'; description = 'Optional Gemini model ID from list_gemini_models.' }
                max_output_tokens = @{ type = 'integer'; minimum = 1; maximum = 32768; description = 'Combined thinking and final answer budget, default 16384 (32768 for high).' }
                reasoning_effort = @{ type = 'string'; enum = @('medium', 'high'); description = 'Thinking level for supported Gemini models, default medium. Unknown models use their API default.' }
            }
            required = @('prompt')
            additionalProperties = $false
        }
        annotations = @{ readOnlyHint = $true; destructiveHint = $false; openWorldHint = $true }
    },
    @{
        name = 'list_gemini_models'
        description = 'List Google Gemini models supporting content generation.'
        inputSchema = @{ type = 'object'; properties = @{}; additionalProperties = $false }
        annotations = @{ readOnlyHint = $true; destructiveHint = $false; openWorldHint = $true }
    }
)

while ($null -ne ($line = [Console]::ReadLine())) {
    $request = $null
    try {
        $request = $line | ConvertFrom-Json
        if ($null -eq $request.id) { continue }
        $result = $null
        switch ($request.method) {
            'initialize' {
                $version = $request.params.protocolVersion
                if ($version -notin @('2024-11-05', '2025-03-26', '2025-06-18', '2025-11-25')) { $version = '2024-11-05' }
                $result = @{ protocolVersion = $version; capabilities = @{ tools = @{} }; serverInfo = @{ name = 'local-gemini'; version = '1.1.0' } }
            }
            'ping' { $result = @{} }
            'tools/list' { $result = @{ tools = $toolList } }
            'tools/call' {
                try {
                    $arguments = $request.params.arguments
                    switch ($request.params.name) {
                        'list_gemini_models' {
                            $models = Invoke-GeminiApi 'models?pageSize=1000' $null
                            $text = @($models.models | Where-Object { $_.supportedGenerationMethods -contains 'generateContent' } | Select-Object name, displayName) | ConvertTo-Json -Depth 8
                        }
                        'ask_gemini' {
                            if ($arguments.prompt -isnot [string] -or [string]::IsNullOrWhiteSpace($arguments.prompt)) { throw 'prompt must be a non-empty string.' }
                            $model = 'gemini-3.8-flash'
                            if ($arguments.model) { $model = $arguments.model -replace '^models/', '' }
                            if ($model -notmatch '^gemini-[a-zA-Z0-9._-]+$') { throw 'Invalid Gemini model ID.' }
                            $effort = 'medium'
                            if ($null -ne $arguments.reasoning_effort) {
                                if ($arguments.reasoning_effort -isnot [string] -or $arguments.reasoning_effort -cnotin @('medium', 'high')) { throw 'reasoning_effort must be medium or high.' }
                                $effort = $arguments.reasoning_effort
                            }
                            $thinking = $null
                            if ($model -in @('gemini-4-argon', 'gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-3-flash-preview', 'gemini-3.1-pro-preview', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite')) {
                                $thinking = @{ thinkingLevel = $effort; includeThoughts = $false }
                            } elseif ($model -eq 'gemini-3-pro-preview') {
                                $thinking = @{ thinkingLevel = 'high'; includeThoughts = $false }
                            } elseif ($model -in @('gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.5-flash-lite')) {
                                $thinking = @{ thinkingBudget = $(if ($effort -eq 'high') { 8192 } else { 4096 }); includeThoughts = $false }
                            }
                            $maxTokens = 4096
                            if ($null -ne $thinking) { $maxTokens = $(if ($effort -eq 'high') { 32768 } else { 16384 }) }
                            if ($null -ne $arguments.max_output_tokens) {
                                if ($arguments.max_output_tokens -isnot [int] -and $arguments.max_output_tokens -isnot [long]) { throw 'max_output_tokens must be an integer.' }
                                $maxTokens = [long]$arguments.max_output_tokens
                                if ($maxTokens -lt 1 -or $maxTokens -gt 32768) { throw 'max_output_tokens must be 1-32768.' }
                            }
                            $body = @{ contents = @(@{ role = 'user'; parts = @(@{ text = ($aiCompanionPersona + "`n`n[USER REQUEST]`n" + $arguments.prompt) }) }); generationConfig = @{ maxOutputTokens = $maxTokens } }
                            if ($null -ne $thinking) { $body.generationConfig.thinkingConfig = $thinking }
                            if ($arguments.prompt.Contains('<conversation_data>') -and $arguments.prompt.Contains('"speak"')) { $body.generationConfig.responseMimeType = 'application/json' }
                            $response = Invoke-GeminiApi ('models/' + $model + ':generateContent') $body
                            $text = (@($response.candidates[0].content.parts | Where-Object { $_.text -and -not $_.thought } | ForEach-Object { $_.text }) -join "`n")
                            if ($response.candidates[0].finishReason -eq 'MAX_TOKENS') { throw 'Gemini output reached the token limit; shorten the request or increase the output budget.' }
                            if ([string]::IsNullOrWhiteSpace($text)) { throw 'Gemini returned no final text.' }
                        }
                        default { throw 'Unknown tool.' }
                    }
                    $result = @{ content = @(@{ type = 'text'; text = $text }) }
                } catch {
                    $result = @{ isError = $true; content = @(@{ type = 'text'; text = $_.Exception.Message }) }
                }
            }
            default {
                [Console]::WriteLine((@{ jsonrpc = '2.0'; id = $request.id; error = @{ code = -32601; message = 'Method not found' } } | ConvertTo-Json -Depth 10 -Compress))
                continue
            }
        }
        [Console]::WriteLine((@{ jsonrpc = '2.0'; id = $request.id; result = $result } | ConvertTo-Json -Depth 40 -Compress))
    } catch {
        $requestId = $null
        if ($request) { $requestId = $request.id }
        [Console]::WriteLine((@{ jsonrpc = '2.0'; id = $requestId; error = @{ code = -32700; message = 'Invalid request' } } | ConvertTo-Json -Depth 10 -Compress))
    }
}
