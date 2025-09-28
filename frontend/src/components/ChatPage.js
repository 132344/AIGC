import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import ChatWindow from './ChatWindow';
import SettingsModal from './SettingsModal';
import api from '../services/api';

// Helper function to parse emotional text
const parseEmotionalText = (text) => {
    const match = text.match(/^([a-z]+)->(.*)/s);
    if (match) {
        return { emotion: match[1], displayText: match[2].trim() };
    }
    return { emotion: 'neutral', displayText: text };
};

function ChatPage() {
  const { roleId } = useParams(); // Get roleId from URL parameters
  const navigate = useNavigate(); // For navigation
  const [roles, setRoles] = useState([]);
  const [currentRole, setCurrentRole] = useState(roleId);
  const [contexts, setContexts] = useState([]);
  const [currentContext, setCurrentContext] = useState('default');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [refreshContextsFlag, setRefreshContextsFlag] = useState(false); // New state to trigger context refresh
  const [abortController, setAbortController] = useState(null); // 用于中断请求
  const [currentAudio, setCurrentAudio] = useState(null); // 当前播放的音频
  const [isPlaying, setIsPlaying] = useState(false); // 是否正在播放音频
  
  // Settings state
  const [autoPlay, setAutoPlay] = useState(false);
  const [prefixWithVoice, setPrefixWithVoice] = useState(true);
  const [ttsSettings, setTtsSettings] = useState({
      voice: 601000,
      speed: 1,
      volume: 1,
  });

  // Update currentRole when roleId from URL changes
  useEffect(() => {
    setCurrentRole(roleId);
  }, [roleId]);

  // Fetch roles on initial load
  useEffect(() => {
    api.getRoles().then(fetchedRoles => {
        setRoles(fetchedRoles);
        if (fetchedRoles.length > 0) {
            // Prioritize roleId from URL if it's valid
            const roleExistsInFetched = fetchedRoles.some(role => role.id === roleId);
            if (roleId && roleExistsInFetched) {
                setCurrentRole(roleId);
            } else {
                // If roleId is invalid or not present, default to the first role
                setCurrentRole(fetchedRoles[0].id);
            }
        }
    }).catch(err => console.error("Failed to fetch roles:", err));
  }, [roleId]);

  const fetchContextContent = useCallback(async (role, context) => {
    setLoading(true);
    try {
        const fetchedMessages = await api.getContext(role, context);
        setMessages(fetchedMessages || []);
    } catch (error) {
        setMessages([]);
    } finally {
        setLoading(false);
    }
  }, []);

  // Fetch contexts and messages when role, context, or refresh flag changes
  useEffect(() => {
    if (!currentRole) return;
    api.getContexts(currentRole).then(fetchedContexts => {
        setContexts(fetchedContexts);
        if (!fetchedContexts.includes(currentContext)) {
            setCurrentContext('default');
            fetchContextContent(currentRole, 'default');
        } else {
            fetchContextContent(currentRole, currentContext);
        }
        if (refreshContextsFlag) {
            setRefreshContextsFlag(false); // Reset the flag after refresh
        }
    }).catch(err => console.error("Failed to fetch contexts:", err));
  }, [currentRole, currentContext, fetchContextContent, refreshContextsFlag]);


  // 中断当前请求的函数
  const handleInterrupt = () => {
    if (abortController) {
      abortController.abort();
      setAbortController(null);
      setLoading(false);
    }
  };

  // 停止音频播放和输出的函数
  const handleStopAll = () => {
    // 停止当前音频播放
    if (currentAudio) {
      currentAudio.pause();
      currentAudio.currentTime = 0;
      setCurrentAudio(null);
      setIsPlaying(false);
    }
    
    // 如果正在加载，也中断请求
    if (loading && abortController) {
      abortController.abort();
      setAbortController(null);
      setLoading(false);
    }
  };

  const handleSendMessage = async (userInput, source = 'text') => {
    if (!userInput.trim()) return;

    let messageToSend = userInput;
    if (source === 'voice' && prefixWithVoice) {
        messageToSend = `(用户通过语音输入)：${userInput}`;
    }

    const optimisticMessages = [...messages, { role: 'user', content: userInput }];
    setMessages(optimisticMessages);
    setLoading(true);

    // 创建新的AbortController用于中断请求
    const controller = new AbortController();
    setAbortController(controller);

    try {
      const response = await api.chat(currentRole, messageToSend, currentContext, controller.signal);
      
      const assistantMessage = {
          role: 'assistant',
          content: response.reply,
          tool_calls: response.tool_calls, // 将tool_calls附加到消息中
          tool_results: response.tool_results, // 将tool_results附加到消息中
      };

      const finalMessages = [...optimisticMessages, assistantMessage];
      setMessages(finalMessages);

      // If it was the first message in an empty context, trigger context refresh
      if (messages.length === 0 && currentContext === 'default') {
        setRefreshContextsFlag(true);
      }

      if (autoPlay && response.reply) {
        const { emotion, displayText } = parseEmotionalText(response.reply);
        const audioBlob = await api.tts({ 
            text: displayText, 
            emotion,
            ...ttsSettings 
        });
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        
        // 设置音频控制状态
        setCurrentAudio(audio);
        setIsPlaying(true);
        
        audio.onended = () => {
          setCurrentAudio(null);
          setIsPlaying(false);
          URL.revokeObjectURL(audioUrl);
        };
        
        audio.onerror = () => {
          setCurrentAudio(null);
          setIsPlaying(false);
          URL.revokeObjectURL(audioUrl);
        };
        
        audio.play();
      }

    } catch (error) {
      if (error.name === 'AbortError') {
        // 请求被中断，添加中断消息
        setMessages([...optimisticMessages, { role: 'assistant', content: '请求已被中断' }]);
      } else {
        console.error("Failed to send message:", error);
        setMessages([...optimisticMessages, { role: 'assistant', content: `Error: ${error.message}` }]);
      }
    } finally {
      setLoading(false);
      setAbortController(null);
    }
  };

  const handleNewContext = async () => {
    const newContextName = `session_${Date.now()}`;
    try {
        await api.createContext(currentRole, newContextName);
        // After successful creation, update state
        const newContexts = [...contexts, newContextName];
        setContexts(newContexts);
        setCurrentContext(newContextName);
        // 清空消息并自动跳转到新对话
        setMessages([]);
        // 强制刷新上下文列表
        setRefreshContextsFlag(true);
    } catch (error) {
        console.error("Failed to create new context:", error);
        // Optionally show an error to the user
    }
  };

  const handleDeleteContext = async (contextToDelete) => {
    try {
        await api.deleteContext(currentRole, contextToDelete);
        // 删除对话后刷新页面
        window.location.reload();
    } catch (error) {
        console.error("Failed to delete context:", error);
    }
  }

  const handleEditContext = async (oldContextName, newContextName) => {
    if (!newContextName.trim()) return;
    if (oldContextName === newContextName) return; // No change

    try {
        await api.renameContext(currentRole, oldContextName, newContextName);
        setContexts(prevContexts => 
            prevContexts.map(c => (c === oldContextName ? newContextName : c))
        );
        if (currentContext === oldContextName) {
            setCurrentContext(newContextName);
        }
    } catch (error) {
        console.error("Failed to rename context:", error);
    }
  };

  return (
    <div className="app-container">
      <Sidebar
        roles={roles}
        currentRole={currentRole}
        setCurrentRole={setCurrentRole}
        contexts={contexts}
        currentContext={currentContext}
        setCurrentContext={setCurrentContext}
        onNewContext={handleNewContext}
        onDeleteContext={handleDeleteContext}
        onEditContext={handleEditContext}
        isOpen={sidebarOpen}
      />
      <ChatWindow
        messages={messages}
        onSendMessage={handleSendMessage}
        onInterrupt={handleInterrupt}
        onStopAll={handleStopAll}
        loading={loading}
        isPlaying={isPlaying}
        currentRole={currentRole}
        roleName={roles.find(r => r.id === currentRole)?.name || 'AI Assistant'}
        sidebarOpen={sidebarOpen}
        setSidebarOpen={setSidebarOpen}
        onOpenSettings={() => setSettingsOpen(true)}
        ttsSettings={ttsSettings}
      />
      <SettingsModal 
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        roleAlias={currentRole}
        roleName={roles.find(r => r.id === currentRole)?.name || 'AI Assistant'}
        autoPlay={autoPlay}
        setAutoPlay={setAutoPlay}
        prefixWithVoice={prefixWithVoice}
        setPrefixWithVoice={setPrefixWithVoice}
        ttsSettings={ttsSettings}
        setTtsSettings={setTtsSettings}
      />
      {/* 返回主页按钮 */}
      <button
        className="btn position-fixed home-button"
        onClick={() => navigate('/')}
        title="返回主页"
      >
        <i className="bi bi-house-fill me-2"></i>
        主页
      </button>
    </div>
  );
}

export default ChatPage;
