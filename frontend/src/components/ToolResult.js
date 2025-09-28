import React from 'react';
import './ToolResult.css';

/**
 * 工具结果显示组件
 * 用于在聊天界面中显示工具调用的结果
 * @param {Object} props - 组件属性
 * @param {Object} props.toolResult - 工具结果对象
 * @param {string} props.toolResult.tool_call_id - 工具调用ID
 * @param {string} props.toolResult.status - 工具执行状态 (success/error)
 * @param {string} props.toolResult.message - 工具执行消息
 * @param {string} props.toolResult.html - 工具返回的HTML内容
 */
const ToolResult = ({ toolResult }) => {
  if (!toolResult) {
    return null;
  }

  const { tool_call_id, status, message, html } = toolResult;

  // 过滤掉message中的工具标签内容，只保留有用的信息
  const filterMessage = (msg) => {
    if (!msg) return null;
    
    // 如果消息只包含工具标签，则不显示
    const toolTagPattern = /^<tool>.*<\/tool>\s*已成功执行.*$/;
    if (toolTagPattern.test(msg.trim())) {
      return null;
    }
    
    // 移除工具标签，保留其他有用信息
    return msg.replace(/<tool>.*?<\/tool>/g, '').trim();
  };

  const filteredMessage = filterMessage(message);

  return (
    <div className={`tool-result ${status === 'success' ? 'tool-result-success' : 'tool-result-error'}`}>
      <div className="tool-result-header">
        <span className="tool-result-title">工具调用结果</span>
        <span className={`tool-result-status ${status === 'success' ? 'status-success' : 'status-error'}`}>
          {status === 'success' ? '✓ 成功' : '✗ 失败'}
        </span>
      </div>
      
      {filteredMessage && (
        <div className="tool-result-message">
          {filteredMessage}
        </div>
      )}
      
      {html && (
        <div 
          className="tool-result-content"
          dangerouslySetInnerHTML={{ __html: html }}
        />
      )}
    </div>
  );
};

export default ToolResult;