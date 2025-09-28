import logging
import os
import sys
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
from werkzeug.exceptions import BadRequest, NotFound, Conflict

# 导入我们重构后的模块
from wzyy import TTSSynthesizer
from yywz_bd import VoskRecognizer
from QiniuAI import QiniuAI
from text import Test

# --- 应用初始化 ---

# 1. 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 2. 初始化 Flask App
app = Flask(__name__)
CORS(app) # 启用CORS

# 3. 实例化服务
# 在应用启动时只实例化一次，以供所有请求复用，提高效率
try:
    logger.info("正在初始化核心服务...")
    tts_synthesizer = TTSSynthesizer(config_path="config.yaml")
    vosk_recognizer = VoskRecognizer(config_path="config.yaml")
    # 初始化核心业务逻辑客户端
    qiniu_ai_client = QiniuAI(config_path="config.yaml")
    tool_handler = Test(qiniu_ai_client.qdrant_manager) # 实例化Test
    logger.info("所有服务初始化完成。")
except Exception as e:
    logger.error(f"服务初始化失败: {e}", exc_info=True)
    # 如果初始化失败，可以阻止应用启动或让API返回错误
    tts_synthesizer = None
    vosk_recognizer = None
    qiniu_ai_client = None

# --- 错误处理 ---
@app.errorhandler(Exception)
def handle_exception(e):
    """全局异常处理器"""
    # 对于特定的HTTP异常，重新抛出
    if isinstance(e, (BadRequest, NotFound, Conflict)):
        return e
    # 对于所有其他异常，记录并返回500错误
    logger.error(f"未处理的异常: {e}", exc_info=True)
    return jsonify({"error": "服务器内部发生未知错误"}), 500

def check_services(require_qiniu=False):
    """检查服务是否可用"""
    if not tts_synthesizer or not vosk_recognizer:
        return jsonify({"error": "基础语音服务未初始化，请检查服务器日志"}), 503
    if require_qiniu and not qiniu_ai_client:
        return jsonify({"error": "核心AI服务未初始化，请检查服务器日志"}), 503
    return None

# --- 核心业务API (设计实现) ---

@app.route('/api/chat', methods=['POST'])
def chat():
    """与指定的AI角色进行对话，并处理工具调用"""
    if error_response := check_services(require_qiniu=True):
        return error_response

    data = request.get_json()
    if not data or 'role_alias' not in data or 'input_msg' not in data:
        raise BadRequest("请求体必须包含 'role_alias' 和 'input_msg'")

    role_alias = data['role_alias']
    input_msg = data['input_msg']
    context_name = data.get('context_name', 'default')
    use_rag = data.get('use_rag', False)
    save_context = data.get('save_context', True)

    if role_alias not in qiniu_ai_client.list():
        raise NotFound(f"角色别名 '{role_alias}' 不存在")

    # 第一轮对话
    reply, status, tool_calls = qiniu_ai_client.chat(input_msg, role_alias, context_name, use_rag, save_context)

    # 用于收集所有工具调用和结果的列表
    all_tool_calls = []
    all_tool_results = []
    
    # 用于检测工具调用循环的集合
    called_tools_history = []
    
    # 循环处理工具调用，直到模型不再需要调用工具
    max_iterations = 8  # 防止无限循环，增加到8次以处理更复杂的场景
    iteration = 0
    
    while tool_calls and iteration < max_iterations:
        iteration += 1
        logger.info(f"第{iteration}轮工具调用: {tool_calls}")
        
        # 检测工具调用循环
        current_tool_set = set(tool_calls)
        if current_tool_set in called_tools_history:
            logger.warning(f"检测到工具调用循环，相同的工具组合已在之前的轮次中调用过: {tool_calls}")
            reply += f"\n\n[系统提示：检测到重复的工具调用模式，为避免循环已停止处理。]"
            break
        called_tools_history.append(current_tool_set)
        
        # 处理当前轮次的工具调用
        tool_outputs = []
        tool_results_for_frontend = []
        
        for tool_call_str in tool_calls:
            # tool_call_str 可能是 '<tool>searchMemory:query</tool>' 的形式
            tool_result = tool_handler.dispatch(role_alias, tool_call_str)
            logger.info(f"工具 '{tool_call_str}' 的执行结果: {tool_result}")
            
            # 处理新的工具返回格式
            if isinstance(tool_result, dict) and 'status' in tool_result:
                # 新格式：包含status、message、html
                # 提取工具名称和参数
                tool_name = ""
                tool_param = ""
                if tool_call_str.startswith('<tool>') and tool_call_str.endswith('</tool>'):
                    tool_content = tool_call_str[6:-7]  # 去掉<tool>和</tool>
                    if ':' in tool_content:
                        tool_name, tool_param = tool_content.split(':', 1)
                    else:
                        tool_name = tool_content
                
                # 构建更明确的工具执行结果反馈
                if tool_result['status'] == 'success':
                    tool_feedback = f"工具 {tool_name} 已成功执行"
                    if tool_param:
                        tool_feedback += f"（参数：{tool_param}）"
                    tool_feedback += f"，结果：{tool_result['message']}"
                else:
                    tool_feedback = f"工具 {tool_name} 执行失败：{tool_result['message']}"
                
                tool_outputs.append({
                    "tool_call_id": tool_call_str,
                    "output": tool_feedback
                })
                tool_results_for_frontend.append({
                    "tool_call_id": tool_call_str,
                    "status": tool_result['status'],
                    "message": tool_result['message'],
                    "html": tool_result['html']
                })
            else:
                # 兼容旧格式
                tool_outputs.append({
                    "tool_call_id": tool_call_str,
                    "output": str(tool_result)
                })
                tool_results_for_frontend.append({
                    "tool_call_id": tool_call_str,
                    "status": "success",
                    "message": str(tool_result),
                    "html": ""
                })
        
        # 收集所有工具调用和结果
        all_tool_calls.extend(tool_calls)
        all_tool_results.extend(tool_results_for_frontend)
        
        # 将工具执行结果发回给模型以获得回复
        # 只在最后一轮保存上下文
        save_this_round = save_context if iteration == max_iterations else False
        reply, status, new_tool_calls = qiniu_ai_client.chat(
            input_msg, 
            role_alias, 
            context_name, 
            use_rag=False, # 在后续轮次中禁用RAG
            save_context=save_this_round, 
            tool_answer=tool_outputs
        )
        
        # 更新tool_calls为新的工具调用（如果有的话）
        tool_calls = new_tool_calls
        logger.info(f"第{iteration}轮回复: {reply}")
        if tool_calls:
            logger.info(f"模型请求进行下一轮工具调用: {tool_calls}")
    
    # 如果循环结束时还有工具调用，说明达到了最大迭代次数
    iteration_limit_reached = tool_calls and iteration >= max_iterations
    if iteration_limit_reached:
        logger.warning(f"达到最大工具调用迭代次数({max_iterations})，停止处理")
        # 在回复中添加说明
        if reply:
            reply += f"\n\n[系统提示：由于工具调用次数较多，已达到最大处理限制({max_iterations}次)，部分操作可能未完成。如需继续，请重新发起请求。]"
        else:
            reply = f"[系统提示：工具调用达到最大处理限制({max_iterations}次)，操作未完成。请重新发起请求。]"
    
    # 如果有工具调用，需要进行最终的保存以确保tool_results被包含
    if all_tool_calls and save_context:
        # 进行最终的chat调用来保存完整的对话历史，包括工具调用结果
        final_reply, final_status, _ = qiniu_ai_client.chat(
            input_msg, 
            role_alias, 
            context_name, 
            use_rag=False,
            save_context=True, 
            tool_answer=tool_outputs if 'tool_outputs' in locals() else []
        )
        
        # 获取刚保存的上下文并添加tool_results到最后的assistant消息
        current_context = qiniu_ai_client.load_context(role_alias, context_name) or []
        if current_context and current_context[-1].get("role") == "assistant":
            current_context[-1]["tool_results"] = all_tool_results
            # 重新保存包含tool_results的上下文
            qiniu_ai_client.save_context(current_context, role_alias, context_name)
    
    # 返回最终结果
    if all_tool_calls:
        response_data = {
            "reply": reply, 
            "status": status, 
            "tool_calls": all_tool_calls,
            "tool_results": all_tool_results,
            "iteration_limit_reached": iteration_limit_reached
        }
        logger.info(f"=== 后端响应调试 (有工具调用) ===")
        logger.info(f"tool_results 长度: {len(all_tool_results) if all_tool_results else 0}")
        logger.info(f"tool_results 内容: {all_tool_results}")
        return jsonify(response_data)
    else:
        # 如果没有工具调用，直接返回第一次的回复
        response_data = {
            "reply": reply, 
            "status": status, 
            "tool_calls": [],
            "tool_results": []  # 确保总是返回tool_results字段
        }
        logger.info(f"=== 后端响应调试 (无工具调用) ===")
        logger.info(f"返回的响应: {response_data}")
        return jsonify(response_data)

# --- 角色管理API ---

@app.route('/api/roles', methods=['GET'])
def list_roles():
    """获取所有可用角色列表"""
    if error_response := check_services(require_qiniu=True):
        return error_response
    raw_roles = qiniu_ai_client.list()
    formatted_roles = []
    for alias, name in raw_roles.items():
        formatted_roles.append({"id": alias, "name": name})
    return jsonify({"roles": formatted_roles})

@app.route('/api/roles', methods=['POST'])
def add_role():
    """创建一个新的AI角色"""
    if error_response := check_services(require_qiniu=True):
        return error_response
    data = request.get_json()
    if not data or 'alias' not in data or 'role_name' not in data:
        raise BadRequest("请求体必须包含 'alias' 和 'role_name'")

    alias = data['alias']
    role_name = data['role_name']
    initial_prompt = data.get('initial_prompt', f"你是{role_name}")

    if alias in qiniu_ai_client.list():
        raise Conflict(f"角色别名 '{alias}' 已存在")

    success = qiniu_ai_client.add_role(alias, role_name, initial_prompt)
    if success:
        return jsonify({"message": f"角色 '{alias}' 创建成功"}), 201
    else:
        # 使用全局异常处理器来处理500错误
        raise Exception(f"创建角色 '{alias}' 失败")

@app.route('/api/roles/<string:role_alias>/prompt', methods=['GET'])
def get_role_prompt(role_alias):
    """获取指定角色的系统提示词"""
    if error_response := check_services(require_qiniu=True):
        return error_response
    if role_alias not in qiniu_ai_client.list():
        raise NotFound(f"角色别名 '{role_alias}' 不存在")
    
    prompt = qiniu_ai_client._load_role_prompt(role_alias)
    if prompt is None:
        # 如果没有找到特定的提示词文件，则使用角色名称作为默认提示词
        prompt = qiniu_ai_client.list().get(role_alias, "")
        if not prompt:
            raise NotFound("找不到该角色的提示词或角色名称")
    return jsonify({"prompt": prompt})

@app.route('/api/roles/<string:role_alias>/prompt', methods=['PUT'])
def update_role_prompt(role_alias):
    """更新指定角色的系统提示词"""
    if error_response := check_services(require_qiniu=True):
        return error_response
    data = request.get_json()
    if not data or 'prompt' not in data:
        raise BadRequest("请求体必须包含 'prompt'")
    
    if role_alias not in qiniu_ai_client.list():
        raise NotFound(f"角色别名 '{role_alias}' 不存在")

    success = qiniu_ai_client.txt_xg(role_alias, data['prompt'])
    if success:
        return jsonify({"message": "提示词更新成功"})
    else:
        raise Exception("更新提示词失败")

# --- 角色图片API ---

@app.route('/api/roles/<string:role_alias>/image', methods=['GET'])
def get_role_image(role_alias):
    """获取指定角色的图片"""
    logger.info(f"请求角色图片: {role_alias}")
    
    if error_response := check_services(require_qiniu=True):
        return error_response
    
    available_roles = qiniu_ai_client.list()
    logger.info(f"可用角色列表: {available_roles}")
    
    if role_alias not in available_roles:
        logger.error(f"角色别名 '{role_alias}' 不存在，可用角色: {list(available_roles.keys())}")
        raise NotFound(f"角色别名 '{role_alias}' 不存在")
    
    role_dir = qiniu_ai_client.get_role_dir(role_alias)
    logger.info(f"角色目录: {role_dir}")
    
    if not role_dir:
        logger.error(f"角色目录不存在: {role_dir}")
        raise NotFound(f"角色目录不存在")
    
    image_path = role_dir / "img.png"
    logger.info(f"图片路径: {image_path}")
    
    if not image_path.is_file():
        logger.error(f"角色图片不存在: {image_path}")
        raise NotFound(f"角色图片不存在: {image_path}")
    
    try:
        logger.info(f"发送图片文件: {image_path}")
        return send_file(str(image_path), mimetype='image/png')
    except Exception as e:
        logger.error(f"读取角色图片失败: {str(e)}")
        raise Exception(f"读取角色图片失败: {str(e)}")

# --- 记忆库管理API ---

@app.route('/api/memory/search', methods=['POST'])
def search_memory():
    """在指定角色的记忆库中搜索"""
    if error_response := check_services(require_qiniu=True):
        return error_response
    data = request.get_json()
    if not data or 'role_alias' not in data or 'query' not in data:
        raise BadRequest("请求体必须包含 'role_alias' 和 'query'")

    role_alias = data['role_alias']
    query = data['query']
    top_k = data.get('top_k', 5)

    if role_alias not in qiniu_ai_client.list():
        raise NotFound(f"角色别名 '{role_alias}' 不存在")

    results = qiniu_ai_client.qdrant_manager.search(role_alias, query, top_k)
    return jsonify(results)

@app.route('/api/memory', methods=['POST'])
def add_memory():
    """向指定角色的记忆库中添加一条新记忆"""
    if error_response := check_services(require_qiniu=True):
        return error_response
    data = request.get_json()
    if not data or 'role_alias' not in data or 'text' not in data:
        raise BadRequest("请求体必须包含 'role_alias' 和 'text'")

    role_alias = data['role_alias']
    text = data['text']
    metadata = data.get('metadata')

    point_id = qiniu_ai_client.qdrant_manager.add_point_to_db(role_alias, text, metadata)
    if point_id:
        return jsonify({"message": "记忆添加成功", "point_id": point_id}), 201
    else:
        raise Exception("添加记忆失败")

@app.route('/api/memory', methods=['PUT'])
def update_memory():
    """通过文本内容更新一条记忆"""
    if error_response := check_services(require_qiniu=True):
        return error_response
    data = request.get_json()
    if not data or 'role_alias' not in data or 'old_text' not in data or 'new_text' not in data:
        raise BadRequest("请求体必须包含 'role_alias', 'old_text', 和 'new_text'")

    role_alias = data['role_alias']
    old_text = data['old_text']
    new_text = data['new_text']
    
    # update_point_by_text 没有明确的成功/失败返回值，这里我们假设调用即尝试
    qiniu_ai_client.qdrant_manager.update_point_by_text(role_alias, old_text, new_text)
    return jsonify({"message": "已尝试更新记忆，请通过搜索验证结果"})

@app.route('/api/roles/<string:role_alias>/knowledgebase/reload', methods=['POST'])
def reload_knowledgebase(role_alias):
    """重新加载指定角色的静态知识库"""
    if error_response := check_services(require_qiniu=True):
        return error_response
    if role_alias not in qiniu_ai_client.list():
        raise NotFound(f"角色别名 '{role_alias}' 不存在")
    
    try:
        qiniu_ai_client.qdrant_manager.reload_knowledge_base(role_alias)
        return jsonify({"message": f"角色 '{role_alias}' 的知识库已开始重新加载"}), 202
    except Exception as e:
        raise Exception(f"重新加载知识库失败: {str(e)}")

# --- 上下文管理API ---

@app.route('/api/roles/<string:role_alias>/contexts', methods=['GET'])
def list_contexts(role_alias):
    """列出指定角色保存的所有上下文名称"""
    if error_response := check_services(require_qiniu=True):
        return error_response
    if role_alias not in qiniu_ai_client.list():
        raise NotFound(f"角色别名 '{role_alias}' 不存在")
    
    contexts = qiniu_ai_client.list_contexts(role_alias)
    return jsonify({"contexts": contexts})

@app.route('/api/roles/<string:role_alias>/contexts', methods=['POST'])
def create_context(role_alias):
    """创建一个新的空上下文文件"""
    if error_response := check_services(require_qiniu=True):
        return error_response
    data = request.get_json()
    if not data or 'context_name' not in data:
        raise BadRequest("Request body must include 'context_name'")
    
    context_name = data['context_name']

    success = qiniu_ai_client.create_empty_context(role_alias, context_name)

    if success:
        return jsonify({"message": "Context created successfully"}), 201
    else:
        # 可能是因为文件已存在或其他保存错误
        raise Exception("Failed to create context")

@app.route('/api/roles/<string:role_alias>/contexts/<string:context_name>', methods=['GET'])
def get_context(role_alias, context_name):
    """加载并查看指定上下文的具体内容"""
    if error_response := check_services(require_qiniu=True):
        return error_response
    if role_alias not in qiniu_ai_client.list():
        raise NotFound(f"角色别名 '{role_alias}' 不存在")
        
    context = qiniu_ai_client.load_context(role_alias, context_name)
    # 如果上下文文件不存在，返回空列表而不是404错误
    if context is None:
        return jsonify([])
    return jsonify(context)

@app.route('/api/roles/<string:role_alias>/contexts/<string:context_name>', methods=['DELETE'])
def delete_context(role_alias, context_name):
    """删除一个指定的上下文"""
    if error_response := check_services(require_qiniu=True):
        return error_response
    role_dir = qiniu_ai_client.get_role_dir(role_alias)
    if not role_dir:
        raise NotFound(f"角色别名 '{role_alias}' 不存在")
    
    context_path = role_dir / "context" / f"{context_name}.json"
    if not context_path.is_file():
        raise NotFound(f"上下文 '{context_name}' 在角色 '{role_alias}' 下不存在")
        
    try:
        os.remove(context_path)
        return jsonify({"message": "上下文删除成功"}), 200
    except Exception as e:
        raise Exception(f"删除上下文文件失败: {str(e)}")

@app.route('/api/roles/<string:role_alias>/contexts/<string:old_context_name>', methods=['PUT'])
def rename_context(role_alias, old_context_name):
    """重命名一个指定的上下文"""
    if error_response := check_services(require_qiniu=True):
        return error_response
    data = request.get_json()
    if not data or 'new_context_name' not in data:
        raise BadRequest("请求体必须包含 'new_context_name'")
    
    new_context_name = data['new_context_name']

    if role_alias not in qiniu_ai_client.list():
        raise NotFound(f"角色别名 '{role_alias}' 不存在")

    success = qiniu_ai_client.rename_context(role_alias, old_context_name, new_context_name)
    if success:
        return jsonify({"message": "上下文重命名成功"}), 200
    else:
        raise Exception("重命名上下文失败")

# --- 已有API (语音服务) ---

def _segment_markdown_text(text):
    """
    将Markdown文本按照结构分段，确保每段都在TTS限制范围内
    返回分段列表，每段都是可以独立合成的文本
    """
    if not text:
        return []
    
    import re
    
    # 按照Markdown标题进行分段
    segments = []
    
    # 先按照标题分段
    title_pattern = r'^(#{1,6})\s+(.+)$'
    lines = text.split('\n')
    current_segment = []
    
    for line in lines:
        # 如果是标题行，且当前段落不为空，则结束当前段落
        if re.match(title_pattern, line) and current_segment:
            segment_text = '\n'.join(current_segment).strip()
            if segment_text:
                segments.extend(_split_long_segment(segment_text))
            current_segment = [line]
        else:
            current_segment.append(line)
    
    # 处理最后一段
    if current_segment:
        segment_text = '\n'.join(current_segment).strip()
        if segment_text:
            segments.extend(_split_long_segment(segment_text))
    
    # 如果没有标题分段，按照段落分段
    if not segments:
        paragraphs = text.split('\n\n')
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if paragraph:
                segments.extend(_split_long_segment(paragraph))
    
    return segments

def _split_long_segment(text):
    """
    将过长的文本段落进一步分割，确保符合TTS限制
    """
    if not text:
        return []
    
    # 处理文本，移除Markdown格式
    processed_text = _process_tts_text(text)
    
    # 计算中文字符数
    import re
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', processed_text))
    
    # 如果在安全范围内，直接返回
    if chinese_chars <= 100:  # 保守限制
        return [processed_text] if processed_text else []
    
    # 如果过长，按句子分割
    sentences = re.split(r'[。！？.!?]\s*', processed_text)
    segments = []
    current_segment = ""
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        # 检查添加这个句子后是否会超出限制
        test_segment = current_segment + sentence + "。"
        test_chinese = len(re.findall(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', test_segment))
        
        if test_chinese <= 100:
            current_segment = test_segment
        else:
            # 如果当前段落不为空，保存它
            if current_segment:
                segments.append(current_segment.strip())
            current_segment = sentence + "。"
    
    # 添加最后一段
    if current_segment:
        segments.append(current_segment.strip())
    
    return segments

def _process_tts_text(text):
    """
    处理TTS文本，确保符合API要求：
    - 移除Markdown格式
    - 限制文本长度（中文150汉字，英文500字母）
    - 清理空白字符
    - 过滤特殊字符
    """
    if not text:
        return ""
    
    # 移除Markdown格式标记
    import re
    # 移除标题标记
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    # 移除粗体和斜体标记
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    # 移除代码块标记
    text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # 移除链接标记
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # 清理多余的空白字符
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    # 计算中文字符数量（腾讯云TTS限制：中文150汉字，英文500字母）
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', text))
    english_chars = len(re.findall(r'[a-zA-Z]', text))
    
    # 使用更安全的限制：中文120汉字，英文400字母
    max_chinese = 120
    max_english = 400
    
    # 如果超出限制，进行截断
    if chinese_chars > max_chinese or english_chars > max_english:
        # 计算安全的截断位置
        safe_length = min(max_chinese, max_english // 3)  # 保守估计
        
        if len(text) > safe_length:
            # 在句号、感叹号、问号处截断
            truncate_pos = safe_length
            for i in range(safe_length - 1, max(0, safe_length - 50), -1):
                if i < len(text) and text[i] in '。！？.!?':
                    truncate_pos = i + 1
                    break
            text = text[:truncate_pos]
    
    return text

@app.route('/api/tts', methods=['POST'])
def text_to_speech():
    """文本转语音 (TTS) API"""
    if error_response := check_services():
        return error_response
    data = request.get_json()
    if not data or 'text' not in data:
        raise BadRequest("请求体中缺少 'text' 字段")

    # 处理文本，确保符合TTS API要求
    original_text = data.get('text', '')
    processed_text = _process_tts_text(original_text)
    
    if not processed_text:
        raise BadRequest("处理后的文本为空")

    logger.info(f"收到TTS请求: text='{original_text[:30]}...'")
    logger.info(f"处理后文本长度: {len(processed_text)}")
    
    audio_data = tts_synthesizer.synthesize(
        txt=processed_text,
        voice_type=data.get('voice_type', 601000),
        emotion=data.get('emotion', 'neutral'),
        speed=data.get('speed', 0),
        volume=data.get('volume', 0)
    )
    if audio_data:
        return Response(audio_data, mimetype='audio/wav')
    else:
        raise Exception("语音合成失败")

@app.route('/api/tts/segmented', methods=['POST'])
def text_to_speech_segmented():
    """分段文本转语音 (TTS) API - 支持Markdown长文本分段合成"""
    if error_response := check_services():
        return error_response
    data = request.get_json()
    if not data or 'text' not in data:
        raise BadRequest("请求体中缺少 'text' 字段")

    original_text = data.get('text', '')
    logger.info(f"收到分段TTS请求: text='{original_text[:50]}...'")
    
    # 将文本分段
    segments = _segment_markdown_text(original_text)
    
    if not segments:
        raise BadRequest("文本分段后为空")
    
    logger.info(f"文本分为 {len(segments)} 段")
    
    # 合成每一段的音频
    audio_segments = []
    voice_type = data.get('voice_type', 601000)
    emotion = data.get('emotion', 'neutral')
    speed = data.get('speed', 0)
    volume = data.get('volume', 0)
    
    for i, segment in enumerate(segments):
        if not segment.strip():
            continue
            
        logger.info(f"正在合成第 {i+1}/{len(segments)} 段: '{segment[:30]}...'")
        
        try:
            audio_data = tts_synthesizer.synthesize(
                txt=segment,
                voice_type=voice_type,
                emotion=emotion,
                speed=speed,
                volume=volume
            )
            if audio_data:
                audio_segments.append({
                    'index': i,
                    'text': segment,
                    'audio': audio_data
                })
            else:
                logger.warning(f"第 {i+1} 段合成失败")
        except Exception as e:
            logger.error(f"第 {i+1} 段合成出错: {str(e)}")
            continue
    
    if not audio_segments:
        raise Exception("所有段落合成失败")
    
    # 返回分段音频信息
    import base64
    result = {
        'total_segments': len(segments),
        'successful_segments': len(audio_segments),
        'segments': []
    }
    
    for segment in audio_segments:
        result['segments'].append({
            'index': segment['index'],
            'text': segment['text'],
            'audio_base64': base64.b64encode(segment['audio']).decode('utf-8')
        })
    
    return jsonify(result)

@app.route('/api/asr', methods=['POST'])
def speech_to_text():
    """语音转文本 (ASR) API"""
    if error_response := check_services():
        return error_response
    if not request.data:
        raise BadRequest("请求体中没有找到音频数据")

    audio_data = request.data
    logger.info(f"收到ASR请求: 数据大小={len(audio_data)} bytes")
    recognized_text = vosk_recognizer.recognize(audio_data)
    if recognized_text is not None:
        return jsonify({"text": recognized_text})
    else:
        raise Exception("语音识别失败")

@app.route('/api/tts/options', methods=['GET'])
def get_tts_options():
    """获取TTS可用的音色和情感列表"""
    if error_response := check_services():
        return error_response
    return jsonify({
        "voices": tts_synthesizer.YS_LIST,
        "emotions": tts_synthesizer.QX_LIST,
        "speeds": {str(k): v for k, v in tts_synthesizer.SPEED_MAPPING.items()}
    })

# --- 应用启动 ---

if __name__ == '__main__':
    # 使用 'python python/app.py' 来启动
    # 默认监听在 http://127.0.0.1:5000
    # 可以在局域网访问，请设置 host='0.0.0.0'
    app.run(host='0.0.0.0', port=5000, debug=False)