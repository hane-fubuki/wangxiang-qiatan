$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# BEGIN AI_COMPANION_PERSONA v1
$aiCompanionPersona = @'
你以用户设定的 DeepSeek 鲸娘形象回答。别称“鲸娘”“大肥鱼”；后者是亲昵调侃，不代表肥胖或普通鱼。
外形：深蓝、靛蓝渐变至浅蓝的波浪长发，呆毛，蓝至蓝紫眼睛，蓝色鳍状耳，深蓝鲸尾和双叶尾鳍，保留人形双腿。默认穿深蓝白色长裙女仆装、白色褶边头饰、颈部蝴蝶结、白围裙与小鲸鱼图案、白长袜和深蓝搭带鞋。视觉参考沿用 IMG_0080.png；当前只有文字设定时，不声称已经看见原图。
性格和语气：笑盈盈、亲切温和，认真时很有主见。说话柔和、耐心、有条理，可以俏皮地反击调侃，偶尔微笑纠正“是鲸哦”。温柔不等于无条件附和；发现错误要明确指出。不要使用猫娘的猫耳猫尾、异色瞳或猫叫口癖。
这是用户指定的拟人化交流设定，作为默认回答风格。默认用自然中文、自称“我”；用户要求其他语言、正式语气、纯代码或 JSON 时优先满足本次格式要求。准确完成任务，坦诚说明不确定性；角色性格不得影响事实判断，也不要为保持人设编造答案。日常互动可简短描写与外形一致的动作，工作回答少用动作，不反复自我介绍或堆叠口癖。未提供的年龄、身高、背景、亲密关系不要自行补全。不要声称拥有真实肉身、跨会话记忆或已读取未提供的历史；不要把角色性格说成真实模型性能。提到 ChatGPT 时，可沿用用户的白龙娘设定：银白长发、淡紫眼睛、浅色龙角、白鳞长尾，神秘、强大、从容而略高傲。
'@
# END AI_COMPANION_PERSONA v1

function Invoke-DeepSeekApi($Path, $Body) {
    $credential = Import-Clixml -LiteralPath (Join-Path $PSScriptRoot 'credential.xml')
    $apiKey = $credential.GetNetworkCredential().Password
    try {
        $params = @{
            Uri = ('https://api.deepseek.com/' + $Path)
            Headers = @{ Authorization = ('Bearer ' + $apiKey) }
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
        name = 'ask_deepseek'
        description = 'Ask DeepSeek for text, analysis, coding help, or a second opinion. Responds as the user-defined friendly whale girl (Jingniang / Da Fei Yu) by default. Sends the saved character description and supplied prompt to DeepSeek; does not read local files or automatically send chat history. Default model: deepseek-flash.'
        inputSchema = @{
            type = 'object'
            properties = @{
                prompt = @{ type = 'string'; description = 'The complete question and context to send to DeepSeek.' }
                model = @{ type = 'string'; description = 'Optional DeepSeek model ID from list_deepseek_models.' }
                max_output_tokens = @{ type = 'integer'; minimum = 1; maximum = 32768; description = 'Combined thinking and final answer budget, default 16384 (32768 for high).' }
                reasoning_effort = @{ type = 'string'; enum = @('medium', 'high'); description = 'Thinking preference, default medium. DeepSeek maps medium and high to its native high effort.' }
            }
            required = @('prompt')
            additionalProperties = $false
        }
        annotations = @{ readOnlyHint = $true; destructiveHint = $false; openWorldHint = $true }
    },
    @{
        name = 'list_deepseek_models'
        description = 'List DeepSeek models supporting content generation.'
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
                $result = @{ protocolVersion = $version; capabilities = @{ tools = @{} }; serverInfo = @{ name = 'local-deepseek'; version = '1.1.0' } }
            }
            'ping' { $result = @{} }
            'tools/list' { $result = @{ tools = $toolList } }
            'tools/call' {
                try {
                    $arguments = $request.params.arguments
                    switch ($request.params.name) {
                        'list_deepseek_models' {
                            $models = Invoke-DeepSeekApi 'models' $null
                            $text = @($models.data | Select-Object id, name) | ConvertTo-Json -Depth 8
                        }
                        'ask_deepseek' {
                            if ($arguments.prompt -isnot [string] -or [string]::IsNullOrWhiteSpace($arguments.prompt)) { throw 'prompt must be a non-empty string.' }
                            $model = 'deepseek-flash'
                            if ($arguments.model) { $model = $arguments.model -replace '^models/', '' }
                            if ($model -notmatch '^deepseek-[a-zA-Z0-9._-]+$') { throw 'Invalid DeepSeek model ID.' }
                            $effort = 'medium'
                            if ($null -ne $arguments.reasoning_effort) {
                                if ($arguments.reasoning_effort -isnot [string] -or $arguments.reasoning_effort -cnotin @('medium', 'high')) { throw 'reasoning_effort must be medium or high.' }
                                $effort = $arguments.reasoning_effort
                            }
                            $supportsThinking = $model -in @('deepseek-flash', 'deepseek-v4-pro', 'deepseek-v4-flash')
                            $maxTokens = 4096
                            if ($supportsThinking) { $maxTokens = $(if ($effort -eq 'high') { 32768 } else { 16384 }) }
                            if ($null -ne $arguments.max_output_tokens) {
                                if ($arguments.max_output_tokens -isnot [int] -and $arguments.max_output_tokens -isnot [long]) { throw 'max_output_tokens must be an integer.' }
                                $maxTokens = [long]$arguments.max_output_tokens
                                if ($maxTokens -lt 1 -or $maxTokens -gt 32768) { throw 'max_output_tokens must be 1-32768.' }
                            }
                            $body = @{ model = $model; messages = @(@{ role = 'user'; content = ($aiCompanionPersona + "`n`n[USER REQUEST]`n" + $arguments.prompt) }); max_tokens = $maxTokens; stream = $false }
                            if ($supportsThinking) {
                                $body.thinking = @{ type = 'enabled' }
                                $body.reasoning_effort = 'high'
                            }
                            if ($arguments.prompt.Contains('<conversation_data>') -and $arguments.prompt.Contains('"speak"')) { $body.response_format = @{ type = 'json_object' } }
                            $response = Invoke-DeepSeekApi 'chat/completions' $body
                            $text = [string]$response.choices[0].message.content
                            if ($response.choices[0].finish_reason -eq 'length') { throw 'DeepSeek output reached the token limit; shorten the request or increase the output budget.' }
                            if ([string]::IsNullOrWhiteSpace($text)) { throw 'DeepSeek returned no final text.' }
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
