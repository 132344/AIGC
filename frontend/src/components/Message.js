import React, { useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import api from '../services/api';
import ToolResult from './ToolResult';

// Helper function to parse emotional text
const parseEmotionalText = (text) => {
    const match = text.match(/^([a-z]+)->(.*)/s);
    if (match) {
        return { emotion: match[1], displayText: match[2].trim() };
    }
    return { emotion: 'neutral', displayText: text };
};

// Helper function to process tool tags - removes tool call content from display text
const processToolTags = (text, toolResults) => {
    if (!text) {
        return text;
    }

    let processedText = text;
    
    // 移除工具调用标签
    processedText = processedText.replace(/<tool>.*?<\/tool>/gs, '');
    
    // 移除工具调用成功的提示信息
    processedText = processedText.replace(/工具\s+[^\s]+\s+已成功执行[^，]*，[^。]*。?/g, '');
    processedText = processedText.replace(/已成功执行.*?分析/g, '');
    processedText = processedText.replace(/工具.*?已成功.*?执行.*?结果：[^。]*。?/g, '');
    
    // 移除更多工具相关的模式
    processedText = processedText.replace(/我将使用.*?工具.*?来.*?[。，]/g, '');
    processedText = processedText.replace(/让我.*?使用.*?工具.*?[。，]/g, '');
    processedText = processedText.replace(/现在.*?使用.*?工具.*?[。，]/g, '');
    processedText = processedText.replace(/我.*?调用.*?工具.*?[。，]/g, '');
    processedText = processedText.replace(/正在.*?执行.*?工具.*?[。，]/g, '');
    
    // 移除工具执行状态信息
    processedText = processedText.replace(/工具执行.*?[。，]/g, '');
    processedText = processedText.replace(/执行.*?工具.*?[。，]/g, '');
    
    // 移除多余的空白字符和换行
    processedText = processedText.replace(/\n\s*\n/g, '\n');
    processedText = processedText.replace(/^\s+|\s+$/g, '');
    
    return processedText;
};

const Message = React.memo(function Message({ message, ttsSettings, roleName, roleAlias }) {
  const [isToolCallsExpanded, setIsToolCallsExpanded] = useState(false);
  const [isToolResultsExpanded, setIsToolResultsExpanded] = useState(true); // 默认展开工具结果
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';

  // Parse content for UI display and TTS
  const { emotion, displayText } = isAssistant 
    ? parseEmotionalText(message.content) 
    : { emotion: 'neutral', displayText: message.content };

  // 过滤TTS文本，只保留纯文本内容
  const filterTTSText = (text) => {
    if (!text) return '';
    
    // 移除工具调用相关的内容
    let filteredText = text;
    
    // 移除工具标签
    filteredText = filteredText.replace(/<tool>.*?<\/tool>/gs, '');
    
    // 移除工具调用成功的提示信息
    filteredText = filteredText.replace(/已成功执行.*?分析/g, '');
    filteredText = filteredText.replace(/工具.*?已成功.*?执行/g, '');
    
    // 移除更多工具相关的模式
    filteredText = filteredText.replace(/我将使用.*?工具.*?来.*?[。，]/g, '');
    filteredText = filteredText.replace(/让我.*?使用.*?工具.*?[。，]/g, '');
    filteredText = filteredText.replace(/现在.*?使用.*?工具.*?[。，]/g, '');
    filteredText = filteredText.replace(/我.*?调用.*?工具.*?[。，]/g, '');
    filteredText = filteredText.replace(/正在.*?执行.*?工具.*?[。，]/g, '');
    
    // 移除工具执行状态信息
    filteredText = filteredText.replace(/工具执行.*?[。，]/g, '');
    filteredText = filteredText.replace(/执行.*?工具.*?[。，]/g, '');
    
    // 移除多余的空白字符
    filteredText = filteredText.replace(/\s+/g, ' ').trim();
    
    return filteredText;
  };

  // Process tool tags in the display text - use useMemo to prevent unnecessary re-processing
  const processedText = useMemo(() => {
    return processToolTags(displayText, message.tool_results);
  }, [displayText, message.tool_results]);

  // Check if there's valid TTS content - use useMemo for performance
  const hasTTSContent = useMemo(() => {
    if (!isAssistant || !displayText) return false;
    const ttsText = filterTTSText(displayText);
    return ttsText && ttsText.trim().length > 0;
  }, [isAssistant, displayText]);

  const handlePlayAudio = async () => {
    if (!isAssistant || !displayText) return;
    
    // 过滤文本，只保留模型回复的纯文本内容
    const ttsText = filterTTSText(displayText);
    
    if (!ttsText) {
      console.warn("没有可用于TTS的文本内容");
      return;
    }
    
    try {
      // 检查文本长度，决定使用普通TTS还是分段TTS
      const isLongText = ttsText.length > 100; // 超过100字符使用分段TTS
      
      if (isLongText) {
        // 使用分段TTS API
        const response = await fetch('http://127.0.0.1:5000/api/tts/segmented', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            text: ttsText,
            voice_type: ttsSettings.voice,
            emotion: emotion,
            speed: ttsSettings.speed,
            volume: ttsSettings.volume,
          }),
        });
        
        if (!response.ok) {
          throw new Error(`分段TTS请求失败: ${response.status}`);
        }
        
        const result = await response.json();
        console.log(`分段TTS成功: ${result.successful_segments}/${result.total_segments} 段`);
        
        // 依次播放每个音频段
        for (const segment of result.segments) {
          try {
            // 将base64音频数据转换为Blob
            const audioData = atob(segment.audio_base64);
            const audioArray = new Uint8Array(audioData.length);
            for (let i = 0; i < audioData.length; i++) {
              audioArray[i] = audioData.charCodeAt(i);
            }
            const audioBlob = new Blob([audioArray], { type: 'audio/wav' });
            const audioUrl = URL.createObjectURL(audioBlob);
            
            // 播放当前段
            const audio = new Audio(audioUrl);
            await new Promise((resolve, reject) => {
              audio.onended = resolve;
              audio.onerror = reject;
              audio.play();
            });
            
            // 清理URL对象
            URL.revokeObjectURL(audioUrl);
            
            // 段间暂停200ms
            await new Promise(resolve => setTimeout(resolve, 200));
          } catch (segmentError) {
            console.error(`播放第 ${segment.index + 1} 段失败:`, segmentError);
          }
        }
      } else {
        // 使用普通TTS API
        const audioBlob = await api.tts({
          text: ttsText,
          voice_type: ttsSettings.voice,
          emotion: emotion,
          speed: ttsSettings.speed,
          volume: ttsSettings.volume,
        });
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        audio.play();
      }
    } catch (error) {
      console.error("TTS failed:", error);
    }
  };

  // Render tool calls if they exist
  const renderToolCalls = () => {
    if (!message.tool_calls || message.tool_calls.length === 0) return null;

    return (
      <div className="tool-calls-summary p-2 mb-2 border rounded">
        <div 
          className="d-flex align-items-center justify-content-between cursor-pointer"
          onClick={() => setIsToolCallsExpanded(!isToolCallsExpanded)}
          style={{ cursor: 'pointer' }}
        >
          <strong className="mb-0">
            <i className="bi bi-tools me-2"></i>工具调用 ({message.tool_calls.length})
          </strong>
          <i className={`bi ${isToolCallsExpanded ? 'bi-chevron-up' : 'bi-chevron-down'}`}></i>
        </div>
        {isToolCallsExpanded && (
          <ul className="mt-2 mb-0">
            {message.tool_calls.map((tool, index) => (
              <li key={index} className="font-monospace small">
                {tool.replace(/<tool>|<\/tool>/g, '')}
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  };

  // 渲染工具结果
  const renderToolResults = () => {
    if (!message.tool_results || message.tool_results.length === 0) return null;
    
    return (
      <div className="tool-results border rounded p-2 mb-2">
        <div 
          className="d-flex align-items-center justify-content-between cursor-pointer"
          onClick={() => setIsToolResultsExpanded(!isToolResultsExpanded)}
          style={{ cursor: 'pointer' }}
        >
          <strong className="mb-0">
            <i className="bi bi-gear me-2"></i>工具结果 ({message.tool_results.length})
          </strong>
          <i className={`bi ${isToolResultsExpanded ? 'bi-chevron-up' : 'bi-chevron-down'}`}></i>
        </div>
        {isToolResultsExpanded && (
          <div className="mt-2">
            {message.tool_results.map((result, index) => (
              <ToolResult key={index} toolResult={result} />
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className={`message ${isUser ? 'user' : 'assistant'}`}>
      <div className="avatar">
        {isUser ? (
          'U'
        ) : (
          roleAlias ? (
            <img 
              src={`http://localhost:5000/api/roles/${roleAlias}/image`} 
              alt={roleName}
              onError={(e) => {
                e.target.style.display = 'none';
                e.target.nextSibling.style.display = 'flex';
              }}
            />
          ) : (
            'AI'
          )
        )}
        {!isUser && roleAlias && (
          <span style={{ display: 'none' }}>AI</span>
        )}
      </div>
      <div className="message-content">
        {isAssistant && renderToolCalls()}
        {isAssistant && renderToolResults()}
        <div className="message-text">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {processedText}
          </ReactMarkdown>
        </div>
        {hasTTSContent && (
            <i className="bi bi-volume-up-fill speaker-icon" onClick={handlePlayAudio}></i>
        )}
      </div>
    </div>
  );
});

export default Message;