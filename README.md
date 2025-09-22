# 问题思考
```txt
Q:你计划将这个应用面向什么类型的用户？这些类型的用户他们面临什么样的痛点，你设想的用户故事是什么样呢？
1.文化娱乐爱好者：文学、影视、游戏等领域的粉丝群体
休闲娱乐用户：寻求新奇互动体验的普通用户
2.无法与喜爱的虚构或历史人物进行沉浸式互动
3.
Q:你认为这个 APP 需要哪些功能？这些功能各自的优先级是什么？你计划本次开发哪些功能？
1.文本和语音对话。优先级：1
2.角色选择。优先级：1
3.角色长期记忆功能。优先级：2
4.角色技能功能。优先级：3
Q:你计划采纳哪家公司的哪个 LLM 模型能力？你对比了哪些，你为什么选择用该 LLM 模型？
目前考虑免费
Q:你期望 AI 角色除了语音聊天外还应该有哪些技能？

```
# 基础需求分析
## 角色搜索

## 文本对话
使用七牛云的"X-Ai/Grok 4 Fast"模型
``` python
import requests

url = "https://openai.qiniu.com/v1/chat/completions"
headers = {
    "Authorization": "Bearer <API_KEY>",
    "Content-Type": "application/json"
}
payload = {
    "stream": False,
    "model": "x-ai/grok-4-fast",
    "messages": [
        {
            "role": "system",
            "content": "You are a helpful assistant."
        },
        {
            "role": "user",
            "content": "Hello!"
        }
    ]
}

response = requests.post(url, json=payload, headers=headers)
print(response.json())
```
## 语音对话
输入
``` python
import requests

url = "https://openai.qiniu.com/v1/voice/asr"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer <API_KEY>"
}
data = {
    "model": "asr",
    "audio": {
        "format": "mp3",
        "url": "http://idh.qnaigc.com/voicetest.mp3"
    }
}

response = requests.post(url, headers=headers, json=data)
print(response.json())
```
输出
``` python
import requests

url = "https://openai.qiniu.com/v1/voice/tts"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer <API_KEY>"
}
data = {
    "audio": {
        "voice_type": "zh_male_M392_conversation_wvae_bigtts",
        "encoding": "mp3"
        "speed_ratio": 1.0
    },
    "request": {
        "text": "你好，世界！"
    }
}

response = requests.post(url, headers=headers, json=data)
print(response.json())
```
# 通用工具
## 记忆搜索
```commandline

```
## 记忆和角色存储
``` commandline
list
/角色名
./上下文
./工具代码
```
# 角色选择
## 原神-伊涅芙
### 独立工具设计
[1] 
[2] 
[3] 
## 
### 独立工具设计

## 
### 独立工具设计

# 详细需求分析
