import sys
from Qdrant import QdrantManager

import re

class Test:
    def __init__(self, manager):
        self.manager = manager

    def dispatch(self, role_alias: str, tool_call_string: str) -> str:
        """
        总控方法：解析并分发工具调用。
        """
        # 动态导入自身模块以查找角色专属类
        text_module = sys.modules[__name__]

        # 1. 初始化角色专属工具类（如果存在）
        role_specific_tools = None
        if hasattr(text_module, role_alias):
            role_class = getattr(text_module, role_alias)
            role_specific_tools = role_class()

        # 2. 解析工具调用
        match = re.search(r"<tool>(.*?)</tool>", tool_call_string)
        if not match:
            return f"错误: 无效的工具调用格式: {tool_call_string}"
        
        call_str = match.group(1).strip()
        parts = call_str.split(':', 1)
        tool_name = parts[0]
        params_str = parts[1] if len(parts) > 1 else ""
        params = params_str.split(':')

        # 3. 查找并执行方法 (优先角色专属工具)
        method_to_call = None
        is_generic = False

        if role_specific_tools and hasattr(role_specific_tools, tool_name):
            method_to_call = getattr(role_specific_tools, tool_name)
        elif hasattr(self, tool_name):
            method_to_call = getattr(self, tool_name)
            is_generic = True
        
        if not method_to_call:
            return f"错误: 未知的工具 '{tool_name}'"

        # 4. 执行并返回结果
        try:
            if is_generic:
                # 通用工具需要传入 role_alias
                result = method_to_call(role_alias, *params)
            else:
                # 角色专属工具直接传入参数
                result = method_to_call(*params)
            
            # 处理新的返回格式（字典格式包含status、message、html）
            if isinstance(result, dict) and 'status' in result:
                return result
            else:
                # 兼容旧格式，转换为新格式
                return {"status": "success", "message": str(result), "html": ""}
        except Exception as e:
            return {"status": "error", "message": f"执行工具 '{tool_name}' 时发生异常: {e}", "html": ""}
    def test(self):
        return """===工具调用===
工具调用规则：
1. 使用<tool>工具名:参数</tool>格式调用工具
2. 工具调用时不要有多余的输出，请只调用工具的内容
工具调用方式：
记忆搜索：<tool>searchMemory:[数量]:搜索内容</tool> (数量可选,1-20,默认3)
记忆添加：<tool>addMemory:添加内容</tool>
记忆更新：<tool>updateMemory:旧内容:新内容</tool>
"""
    def searchMemory(self, name, *args):
        top_k = 5  # 默认值
        txt = ""

        if not args:
            return "错误：搜索内容不能为空。"

        try:
            # 尝试解析第一个参数作为 top_k (新格式)
            parsed_k = int(args[0])
            if len(args) > 1:
                top_k = parsed_k
                txt = ":".join(args[1:])
            else:
                # 只有一个数字参数，将其视为搜索内容
                txt = args[0]
        except (ValueError, IndexError):
            # 如果第一个参数不是数字，则假定为旧格式
            txt = ":".join(args)

        # 限制 top_k 在 1-20 之间
        top_k = max(1, min(top_k, 20))

        search_results = self.manager.search(name, txt, top_k=top_k)
        if not search_results or (isinstance(search_results, dict) and "error" in search_results):
            return "无搜索结果"
        
        # 提取每个结果字典中的'text'字段
        texts = [str(result.get('text', '')) for result in search_results]
        
        # 将所有文本合并成一个字符串，用换行符分隔
        return "\n".join(texts) if texts else "无搜索结果"
    def addMemory(self,name,txt): 
        point_id = self.manager.add_point_to_db(name, txt)
        return "添加成功" if point_id is not None else "添加失败"
    def updateMemory(self, name, old_txt, new_txt):
        # 1. 先用 old_txt 搜索，找到最匹配的完整原文
        search_results = self.manager.search(name, old_txt, top_k=1)
        
        if not search_results or (isinstance(search_results, dict) and "error" in search_results):
            return f"更新失败：未找到与“{old_txt}”相关的记忆可供更新。"

        # 提取最匹配的结果的原文
        best_match_text = search_results[0].get('text')

        if not best_match_text:
            return f"更新失败：找到匹配项但无法获取原文。"

        # 2. 使用找到的完整原文去执行更新
        update_result = self.manager.update_point_by_text(name, best_match_text, new_txt)
        return update_result

    def get_full_tool_prompt(self, role_alias: str) -> str:
        """
        根据角色别名，生成完整的工具提示词。
        规则：通用工具提示 + 角色专属工具提示
        """
        # 动态导入自身模块以查找角色专属类
        text_module = sys.modules[__name__]
        prompts = []
        
        # 1. 获取通用工具提示
        prompts.append(self.test())
        
        # 2. 获取角色专属工具提示
        if hasattr(text_module, role_alias):
            role_class = getattr(text_module, role_alias)
            prompts.append(role_class().test())
            
        return "\n".join(prompts)


class zgl:
    def test(self):
        return """
战术沙盘：<tool>zhanshushaipan:内容</tool>
兵法比对：<tool>bingfabidui:内容</tool>
出谋卡片：<tool>chumoukapian:内容</tool>
"""
    
    def zhanshushaipan(self, txt):
        """
        战术沙盘：分析战术情况并返回成功/失败状态和HTML内容
        """
        try:
            # 生成战术沙盘的HTML内容
            html_content = f"""
            <div class="tool-result-box zhanshushaipan">
                <div class="tool-header">
                    <i class="bi bi-diagram-3"></i>
                    <h4>战术沙盘</h4>
                </div>
                <div class="tool-content">
                    <div class="battlefield-map">
                        <div class="terrain">地形：{txt}</div>
                        <div class="strategy-points">
                            <div class="point">🏰 主要据点</div>
                            <div class="point">⚔️ 战略要地</div>
                            <div class="point">🛡️ 防御阵地</div>
                        </div>
                        <div class="tactical-analysis">
                            <h5>战术分析</h5>
                            <p>根据当前战况'{txt}'，建议采用以下战术部署：</p>
                            <ul>
                                <li>加强前线防御，巩固既有阵地</li>
                                <li>派遣侦察兵探查敌军动向</li>
                                <li>准备后备力量，随时支援前线</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
            """
            # 返回特殊格式，让模型明确知道工具已执行完成
            return {"status": "success", "message": f"<tool>zhanshushaipan:{txt}</tool> 已成功生成战术沙盘分析", "html": html_content}
        except Exception as e:
            return {"status": "error", "message": f"战术沙盘生成失败：{str(e)}", "html": ""}
    
    def bingfabidui(self, txt):
        """
        兵法比对：比对兵法策略并返回成功/失败状态和HTML内容
        """
        try:
            # 生成兵法比对的HTML内容
            html_content = f"""
            <div class="tool-result-box bingfabidui">
                <div class="tool-header">
                    <i class="bi bi-book"></i>
                    <h4>兵法比对</h4>
                </div>
                <div class="tool-content">
                    <div class="strategy-comparison">
                        <div class="input-strategy">
                            <h5>当前策略</h5>
                            <p>{txt}</p>
                        </div>
                        <div class="classical-strategies">
                            <h5>古典兵法对照</h5>
                            <div class="strategy-item">
                                <strong>孙子兵法·谋攻篇：</strong>
                                <p>"知己知彼，百战不殆"</p>
                            </div>
                            <div class="strategy-item">
                                <strong>三十六计·胜战计：</strong>
                                <p>"瞒天过海，围魏救赵"</p>
                            </div>
                            <div class="strategy-item">
                                <strong>兵法总结：</strong>
                                <p>根据'{txt}'的情况，建议采用灵活机动的战术，避实击虚。</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            """
            return {"status": "success", "message": f"<tool>bingfabidui:{txt}</tool> 已成功完成兵法比对分析", "html": html_content}
        except Exception as e:
            return {"status": "error", "message": f"兵法比对失败：{str(e)}", "html": ""}
    
    def chumoukapian(self, txt):
        """
        出谋卡片：生成策略卡片并返回成功/失败状态和HTML内容
        """
        try:
            # 生成出谋卡片的HTML内容
            html_content = f"""
            <div class="tool-result-box chumoukapian">
                <div class="tool-header">
                    <i class="bi bi-lightbulb"></i>
                    <h4>出谋卡片</h4>
                </div>
                <div class="tool-content">
                    <div class="strategy-card">
                        <div class="card-title">💡 智谋方案</div>
                        <div class="card-content">
                            <div class="situation">
                                <strong>当前情况：</strong>
                                <p>{txt}</p>
                            </div>
                            <div class="strategies">
                                <div class="strategy">
                                    <span class="strategy-number">1</span>
                                    <div class="strategy-text">
                                        <strong>上策：</strong>运筹帷幄，决胜千里
                                    </div>
                                </div>
                                <div class="strategy">
                                    <span class="strategy-number">2</span>
                                    <div class="strategy-text">
                                        <strong>中策：</strong>因势利导，顺水推舟
                                    </div>
                                </div>
                                <div class="strategy">
                                    <span class="strategy-number">3</span>
                                    <div class="strategy-text">
                                        <strong>下策：</strong>以退为进，保存实力
                                    </div>
                                </div>
                            </div>
                            <div class="recommendation">
                                <strong>🎯 推荐方案：</strong>
                                <p>综合考虑当前形势，建议采用上策，主动出击，把握先机。</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            """
            return {"status": "success", "message": f"<tool>chumoukapian:{txt}</tool> 已成功生成出谋卡片", "html": html_content}
        except Exception as e:
            return {"status": "error", "message": f"出谋卡片生成失败：{str(e)}", "html": ""}


class ss:
    def test(self):
        return """
作诗：<tool>zuoshi:内容</tool>
食谱：<tool>shipu:内容</tool>
"""
    
    def zuoshi(self, txt):
        """
        作诗：创作诗歌并返回成功/失败状态和HTML内容
        """
        try:
            # 生成作诗的HTML内容
            html_content = f"""
            <div class="tool-result-box zuoshi">
                <div class="tool-header">
                    <i class="bi bi-feather"></i>
                    <h4>诗歌创作</h4>
                </div>
                <div class="tool-content">
                    <div class="poem-container">
                        <div class="poem-title">📜 以"{txt}"为题</div>
                        <div class="poem-content">
                            <div class="poem-line">春风得意马蹄疾，</div>
                            <div class="poem-line">一日看尽长安花。</div>
                            <div class="poem-line">{txt}如诗意盎然，</div>
                            <div class="poem-line">墨香飘逸满心田。</div>
                        </div>
                        <div class="poem-footer">
                            <div class="poem-style">体裁：七言绝句</div>
                            <div class="poem-mood">意境：清新雅致</div>
                        </div>
                    </div>
                </div>
            </div>
            """
            return {"status": "success", "message": "诗歌创作完成", "html": html_content}
        except Exception as e:
            return {"status": "error", "message": f"诗歌创作失败：{str(e)}", "html": ""}
    
    def shipu(self, txt):
        """
        食谱：制作食谱并返回成功/失败状态和HTML内容
        """
        try:
            # 生成食谱的HTML内容
            html_content = f"""
            <div class="tool-result-box shipu">
                <div class="tool-header">
                    <i class="bi bi-book-half"></i>
                    <h4>美食食谱</h4>
                </div>
                <div class="tool-content">
                    <div class="recipe-container">
                        <div class="recipe-title">🍽️ {txt} 制作指南</div>
                        <div class="recipe-info">
                            <div class="info-item">
                                <strong>难度：</strong>⭐⭐⭐
                            </div>
                            <div class="info-item">
                                <strong>时间：</strong>30分钟
                            </div>
                            <div class="info-item">
                                <strong>人数：</strong>2-3人份
                            </div>
                        </div>
                        <div class="recipe-ingredients">
                            <h5>🥬 所需食材</h5>
                            <ul>
                                <li>主料：根据{txt}特点选择</li>
                                <li>调料：盐、胡椒粉、生抽</li>
                                <li>配菜：时令蔬菜</li>
                            </ul>
                        </div>
                        <div class="recipe-steps">
                            <h5>👩‍🍳 制作步骤</h5>
                            <ol>
                                <li>准备所有食材，清洗干净</li>
                                <li>按照传统工艺进行处理</li>
                                <li>调味炒制，火候适中</li>
                                <li>装盘摆放，色香味俱全</li>
                            </ol>
                        </div>
                    </div>
                </div>
            </div>
            """
            return {"status": "success", "message": "食谱制作完成", "html": html_content}
        except Exception as e:
            return {"status": "error", "message": f"食谱制作失败：{str(e)}", "html": ""}

class ynf:
    def test(self):
        return """
模式切换：<tool>moshiqiehuan:模式名称</tool>
发送表情包：<tool>fasongbiaoqingbao:表情类型</tool>
礼物盒：<tool>ynf_giftbox:选择礼物类型:{花/糖果/道具} 祝福语:"{msg}"</tool>
"""
    
    def moshiqiehuan(self, mode):
        """
        模式切换：切换工作模式并返回成功/失败状态和HTML内容
        """
        try:
            # 生成模式切换的HTML内容
            html_content = f"""
            <div class="tool-result-box moshiqiehuan">
                <div class="tool-header">
                    <i class="bi bi-toggle-on"></i>
                    <h4>模式切换</h4>
                </div>
                <div class="tool-content">
                    <div class="mode-switch">
                        <div class="switch-animation">
                            <div class="mode-indicator active">{mode}</div>
                        </div>
                        <div class="mode-description">
                            <h5>🔄 当前模式：{mode}</h5>
                            <div class="mode-features">
                                <div class="feature">✨ 个性化交互体验</div>
                                <div class="feature">🎯 专属功能优化</div>
                                <div class="feature">💫 智能响应调整</div>
                            </div>
                            <div class="mode-status">
                                <span class="status-badge success">已激活</span>
                                <span class="mode-time">切换时间：{mode}模式已启用</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            """
            return {"status": "success", "message": f"切换到{mode}模式", "html": html_content}
        except Exception as e:
            return {"status": "error", "message": f"模式切换失败：{str(e)}", "html": ""}
    
    def fasongbiaoqingbao(self, emoji_type):
        """
        发送表情包：发送指定类型表情包并返回成功/失败状态和HTML内容
        """
        try:
            # 根据表情类型选择对应的表情
            emoji_map = {
                "开心": "😊😄😃🥰",
                "难过": "😢😭😔💔",
                "惊讶": "😲😱🤯😮",
                "生气": "😠😡🤬💢",
                "可爱": "🥺😘🤗💕",
                "默认": "😊🎉✨💫"
            }
            emojis = emoji_map.get(emoji_type, emoji_map["默认"])
            
            # 生成表情包的HTML内容
            html_content = f"""
            <div class="tool-result-box fasongbiaoqingbao">
                <div class="tool-header">
                    <i class="bi bi-emoji-smile"></i>
                    <h4>表情包发送</h4>
                </div>
                <div class="tool-content">
                    <div class="emoji-container">
                        <div class="emoji-type-title">📱 {emoji_type}表情包</div>
                        <div class="emoji-display">
                            <div class="emoji-grid">
                                {' '.join([f'<span class="emoji-item">{emoji}</span>' for emoji in emojis])}
                            </div>
                        </div>
                        <div class="emoji-message">
                            <div class="message-bubble">
                                <span class="emoji-large">{emojis[0]}</span>
                                <span class="message-text">已为你发送{emoji_type}表情包~</span>
                            </div>
                        </div>
                        <div class="emoji-actions">
                            <button class="action-btn">💝 收藏</button>
                            <button class="action-btn">🔄 换一批</button>
                        </div>
                    </div>
                </div>
            </div>
            """
            return {"status": "success", "message": f"{emoji_type}表情包", "html": html_content}
        except Exception as e:
            return {"status": "error", "message": f"表情包发送失败：{str(e)}", "html": ""}
    
    def ynf_giftbox(self, gift_type, message=""):
        """
        礼物盒：准备礼物盒并返回成功/失败状态和HTML内容
        """
        try:
            # 根据礼物类型选择对应的图标和描述
            gift_map = {
                "花": {"icon": "🌹", "name": "鲜花礼盒", "desc": "精选玫瑰花束，芬芳怡人"},
                "糖果": {"icon": "🍭", "name": "甜蜜糖果", "desc": "手工制作糖果，甜蜜满分"},
                "道具": {"icon": "🎁", "name": "神秘道具", "desc": "特殊道具礼盒，惊喜连连"}
            }
            gift_info = gift_map.get(gift_type, gift_map["道具"])
            
            # 生成礼物盒的HTML内容
            html_content = f"""
            <div class="tool-result-box ynf-giftbox">
                <div class="tool-header">
                    <i class="bi bi-gift"></i>
                    <h4>礼物盒</h4>
                </div>
                <div class="tool-content">
                    <div class="giftbox-container">
                        <div class="gift-animation">
                            <div class="gift-box">
                                <div class="gift-icon">{gift_info['icon']}</div>
                                <div class="gift-sparkles">✨💫⭐</div>
                            </div>
                        </div>
                        <div class="gift-details">
                            <h5>🎀 {gift_info['name']}</h5>
                            <p class="gift-description">{gift_info['desc']}</p>
                            {f'<div class="gift-message"><strong>💌 祝福语：</strong><p class="blessing-text">{message}</p></div>' if message else ''}
                        </div>
                        <div class="gift-actions">
                            <div class="action-buttons">
                                <button class="gift-btn open">🎁 打开礼盒</button>
                                <button class="gift-btn share">💝 分享喜悦</button>
                            </div>
                        </div>
                        <div class="gift-status">
                            <span class="status-text">礼物已准备完毕，等待开启~</span>
                        </div>
                    </div>
                </div>
            </div>
            """
            return {"status": "success", "message": f"{gift_info['name']}准备完成", "html": html_content}
        except Exception as e:
            return {"status": "error", "message": f"礼物盒准备失败：{str(e)}", "html": ""}


if __name__ == '__main__':
    print(Test().test())
