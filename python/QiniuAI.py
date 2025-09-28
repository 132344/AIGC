from typing import List, Dict, Optional, Tuple
import requests
import yaml
import json
import os
from pathlib import Path
import re

# 从 Qdrant.py 导入 QdrantManager
try:
    from Qdrant import QdrantManager
except ImportError:
    print("警告: 未找到 QdrantManager，RAG功能将不可用。")
    QdrantManager = None

# 从 text.py 导入工具处理类
try:
    from text import Test as ToolExecutor
except ImportError:
    print("警告: 未找到 text.py 或 ToolExecutor 类，工具调用功能将受限。")
    ToolExecutor = None

# 七牛云AI API封装类
class QiniuAI:
    
    def __init__(self, config_path: Optional[str] = None, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.roles_dir = Path(__file__).parent.parent / "list"
        self.config_path = config_path if config_path else "config.yaml"
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}
        except FileNotFoundError:
            self.config = {"qdrant": {"db": {}}, "api": {"Qiniu": {}}}
        
        self.config.setdefault("qdrant", {}).setdefault("db", {})
        self._save_config()
        
        self.api_key = api_key or self.config.get("api", {}).get("Qiniu", {}).get("api_key")
        self.base_url = base_url or self.config.get("api", {}).get("Qiniu", {}).get("base_url")
        
        self.default_model = self.config.get('model', {}).get('default_model', "x-ai/grok-4-fast")
        
        # 状态 self.current_role_alias 已被移除以保证线程安全
        
        self.tool_pattern = re.compile(r"<tool>(.*?)</tool>", re.DOTALL)

        if QdrantManager:
            self.qdrant_manager = QdrantManager(config_path=self.config_path, reload_books=False)
        else:
            self.qdrant_manager = None
        
        if ToolExecutor:
            self.tool_executor = ToolExecutor(self.qdrant_manager)
        else:
            self.tool_executor = None

    def _save_config(self) -> None:
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self.config, f, allow_unicode=True)

    def list(self) -> Dict[str, str]:
        return self.config.get("qdrant", {}).get("db", {})

    def get_role_dir(self, role_alias: str) -> Optional[Path]:
        if role_alias in self.list():
            return self.roles_dir / role_alias
        return None

    def list_contexts(self, role_alias: str) -> List[str]:
        role_dir = self.get_role_dir(role_alias)
        if not role_dir: return []
        context_dir = role_dir / "context"
        if not context_dir.is_dir(): return []
        return [f.stem for f in context_dir.glob("*.json")]

    def save_context(self, context: List[Dict], role_alias: str, context_name: str) -> bool:
        role_dir = self.get_role_dir(role_alias)
        if not role_dir: return False
        try:
            context_dir = role_dir / "context"
            context_dir.mkdir(parents=True, exist_ok=True)
            context_path = context_dir / f"{context_name}.json"
            with open(context_path, "w", encoding="utf-8") as f:
                json.dump(context, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存上下文失败: {str(e)}")
            return False

    def load_context(self, role_alias: str, context_name: str) -> Optional[List[Dict]]:
        role_dir = self.get_role_dir(role_alias)
        if not role_dir: return None
        context_path = role_dir / "context" / f"{context_name}.json"
        if context_path.is_file():
            try:
                with open(context_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载上下文失败: {str(e)}")
        return None

    def create_empty_context(self, role_alias: str, context_name: str) -> bool:
        """创建一个新的、只包含系统提示的上下文文件。"""
        if self.load_context(role_alias, context_name) is not None:
            # 上下文文件已存在
            return False

        system_prompt_from_file = self._load_role_prompt(role_alias) or f"你是{self.list().get(role_alias, '')}"
        tool_prompt = ""
        if self.tool_executor:
            tool_prompt = self.tool_executor.get_full_tool_prompt(role_alias)
        
        full_system_prompt = system_prompt_from_file
        if tool_prompt and tool_prompt not in system_prompt_from_file:
             full_system_prompt += "\n\n" + tool_prompt
        
        initial_context = [{"role": "system", "content": full_system_prompt}]
        return self.save_context(initial_context, role_alias, context_name)

    def rename_context(self, role_alias: str, old_context_name: str, new_context_name: str) -> bool:
        """重命名指定角色的上下文文件。"""
        role_dir = self.get_role_dir(role_alias)
        if not role_dir: return False
        
        context_dir = role_dir / "context"
        old_path = context_dir / f"{old_context_name}.json"
        new_path = context_dir / f"{new_context_name}.json"

        if not old_path.is_file():
            print(f"错误: 上下文文件 '{old_context_name}.json' 不存在。")
            return False
        if new_path.is_file():
            print(f"错误: 新上下文文件 '{new_context_name}.json' 已存在。")
            return False
        
        try:
            os.rename(old_path, new_path)
            return True
        except Exception as e:
            print(f"重命名上下文文件失败: {str(e)}")
            return False

    def add_role(self, alias: str, role_name: str, initial_prompt: str = "") -> bool:
        if alias in self.list(): return False
        try:
            self.config["qdrant"]["db"][alias] = role_name
            self._save_config()
            if self.qdrant_manager: self.qdrant_manager.__init__()
            self.txt_xg(alias, initial_prompt or f"你是{role_name}")
            return True
        except Exception as e:
            print(f"添加角色失败: {str(e)}")
            self.config["qdrant"]["db"].pop(alias, None)
            return False

    def _load_role_prompt(self, role_alias: str) -> Optional[str]:
        role_dir = self.get_role_dir(role_alias)
        role_name = self.list().get(role_alias)
        if not role_dir or not role_name: return None
        prompt_path = role_dir / f"{role_name}.txt"
        return prompt_path.read_text(encoding="utf-8").strip() if prompt_path.is_file() else None

    def txt_xg(self, role_alias: str, new_prompt: str) -> bool:
        role_dir = self.get_role_dir(role_alias)
        role_name = self.list().get(role_alias)
        if not role_dir or not role_name: return False
        try:
            # 注入完整的工具提示
            if self.tool_executor:
                tool_prompt = self.tool_executor.get_full_tool_prompt(role_alias)
                full_prompt = new_prompt + "\n\n" + tool_prompt
            else:
                full_prompt = new_prompt

            prompt_path = role_dir / f"{role_name}.txt"
            prompt_path.write_text(new_prompt, encoding="utf-8") # 保存原始prompt
            
            context_names = self.list_contexts(role_alias)
            for name in context_names:
                context = self.load_context(role_alias, name)
                if context:
                    if context[0]["role"] == "system":
                        context[0]["content"] = full_prompt
                    else:
                        context.insert(0, {"role": "system", "content": full_prompt})
                    self.save_context(context, role_alias, name)
            print(f"提示词已更新，并同步到 {len(context_names)} 个上下文中。")
            return True
        except Exception as e:
            print(f"修改提示词并同步上下文失败: {str(e)}")
            return False



    def _send_chat_completion(self, messages: List[Dict]) -> Optional[Dict]:
        if not self.api_key or not self.base_url: raise ValueError("API密钥或基础地址未配置")
        payload = {"stream": False, "model": self.default_model, "messages": messages}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        url = f"{self.base_url}/chat/completions"
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e: return None



    def chat(self, input_msg: str, role_alias: str, context_name: Optional[str] = "default", use_rag: bool = True, save_context: bool = True, tool_answer: Optional[List[Dict]] = None) -> Tuple[str, str, List[Dict]]:
        if role_alias not in self.list(): 
            return f"错误: 别名 '{role_alias}' 不存在。", "error", []
        
        context = self.load_context(role_alias, context_name)
        
        # 准备系统提示词，并确保工具提示存在
        system_prompt_from_file = self._load_role_prompt(role_alias) or f"你是{self.list().get(role_alias, '')}"
        tool_prompt = ""
        if self.tool_executor:
            tool_prompt = self.tool_executor.get_full_tool_prompt(role_alias)
        
        full_system_prompt = system_prompt_from_file
        if tool_prompt and tool_prompt not in system_prompt_from_file:
             full_system_prompt += "\n\n" + tool_prompt

        if not context:
            # 如果没有上下文，创建一个新的
            context = [{"role": "system", "content": full_system_prompt}]
        else:
            # 如果有上下文，检查并更新系统提示
            if context[0]["role"] == "system":
                if context[0]["content"] != full_system_prompt:
                    context[0]["content"] = full_system_prompt
            else:
                context.insert(0, {"role": "system", "content": full_system_prompt})

        messages = context.copy()
        
        # 如果是工具调用的后续步骤
        if tool_answer:
            # 重新添加用户原始输入，为模型提供上下文
            messages.append({"role": "user", "content": input_msg})
            # 将工具的输出添加到消息历史中
            for tool_output in tool_answer:
                messages.append({
                    "role": "tool", 
                    "content": tool_output["output"], 
                    "tool_call_id": tool_output["tool_call_id"]
                })
        else:
            # 如果是对话的第一轮
            rag_content = ""
            if use_rag and self.qdrant_manager:
                search_results = self.qdrant_manager.search(role_alias=role_alias, query=input_msg)
                if search_results and "error" not in search_results:
                    rag_texts = [f"- {item.get('text', '')}" for item in search_results]
                    rag_content = "参考资料：\n" + "\n".join(rag_texts) + "\n\n"
            messages.append({"role": "user", "content": rag_content + input_msg})

        # 在发送前，清理掉API不支持的、仅供前端使用的 tool_calls 字段
        messages_for_api = []
        for msg in messages:
            if msg.get("role") == "assistant" and "tool_calls" in msg:
                # 创建一个没有 'tool_calls' 键的新字典
                cleaned_msg = {k: v for k, v in msg.items() if k != 'tool_calls'}
                messages_for_api.append(cleaned_msg)
            else:
                messages_for_api.append(msg)

        # 发送请求到AI模型
        result = self._send_chat_completion(messages_for_api)
        if not result or not result.get("choices"):
            return "抱歉，我暂时无法回复。", "error", []

        assistant_message = result["choices"][0]["message"]
        messages.append(assistant_message)
        
        tool_calls = []
        # 检查是否有工具调用请求
        if assistant_message.get("tool_calls"):
            # 在新版API中，工具调用在 tool_calls 字段中
            for tool_call in assistant_message["tool_calls"]:
                # 假设 tool_call 是一个包含 id 和 function 的对象
                # 我们需要将其转换为旧的 <tool>string</tool> 格式以兼容 `dispatch`
                # 注意：这需要根据您的 `dispatch` 方法进行调整
                tool_str = f"<tool>{tool_call['function']['name']}:{':'.join(map(str, tool_call['function']['arguments'].values()))}</tool>"
                tool_calls.append(tool_str)
        else:
            # 兼容旧的、通过内容返回工具调用的方式
            assistant_content = assistant_message.get("content", "")
            matches = self.tool_pattern.findall(assistant_content)
            if matches:
                tool_calls = [f"<tool>{match}</tool>" for match in matches]

        # 保存上下文逻辑修复：确保所有对话都能被正确保存
        if save_context and context_name:
            messages_to_save = messages.copy()
            
            # 如果这是工具调用的最终回复（tool_answer存在），需要特殊处理
            if tool_answer:
                # 这是工具调用后的最终回复，需要保存完整的对话流程
                # 确保工具调用信息被正确保存到assistant消息中
                if messages_to_save and messages_to_save[-1]["role"] == "assistant":
                    # 为最终的assistant消息添加工具调用信息，便于前端渲染
                    tool_call_ids = [tool_output["tool_call_id"] for tool_output in tool_answer]
                    messages_to_save[-1]['tool_calls'] = tool_call_ids
                
                self.save_context(messages_to_save, role_alias, context_name)
            elif not tool_calls:
                # 这是普通对话（没有工具调用），直接保存
                self.save_context(messages_to_save, role_alias, context_name)
            # 如果有tool_calls但没有tool_answer，说明这是工具调用的第一阶段
            # 此时不保存，等待工具执行完成后的最终回复时再保存
        
        final_reply = assistant_message.get("content", "")
        return final_reply, "user", tool_calls

    # set_current_role_by_alias 方法已被移除

if __name__ == '__main__':
    print("--- 初始化客户端 ---")
    client = QiniuAI()
    test_alias = 'fy'
    if test_alias not in client.list():
        print(f"为测试做准备，添加角色 '{test_alias}'...")
        client.add_role(test_alias, "翻译助手")
    test_role_name = client.list()[test_alias]
    print(f"测试准备就绪，使用角色别名: '{test_alias}', 角色名: '{test_role_name}'\n")

    # --- 测试场景 ---
    print("--- 1. 创建一个带有人设的对话 ---")
    client.save_context([], test_alias, "cat_test") 
    original_prompt = client._load_role_prompt(test_alias)
    cat_prompt = "你是一只猫，只会说‘喵’。"
    client.txt_xg(test_alias, cat_prompt)
    print(f"提示词已修改为: '{cat_prompt}'")
    reply, _ = client.chat("你是谁？", test_alias, context_name="cat_test")
    print(f"猫人设下，模型回复: '{reply}'")

    print("\n--- 2. 在同一上下文中，再次修改人设 ---")
    dog_prompt = "你是一只狗，只会说‘汪’。"
    client.txt_xg(test_alias, dog_prompt)
    print(f"提示词已修改为: '{dog_prompt}'")
    reply, _ = client.chat("你又是谁？", test_alias, context_name="cat_test")
    print(f"狗人设下，模型回复: '{reply}'")

    client.txt_xg(test_alias, original_prompt)
    print(f"\n提示词已恢复为: '{original_prompt}'")
    reply, _ = client.chat("你是谁？", test_alias, context_name="cat_test")
    print(f"恢复人设后，模型回复: '{reply}'")

    print("\n--- 所有测试完成 ---")
