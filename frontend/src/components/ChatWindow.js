import React, { useState, useRef, useEffect } from 'react';
import Message from './Message';
import api from '../services/api';

function ChatWindow({ messages, onSendMessage, onInterrupt, onStopAll, loading, isPlaying, roleName, currentRole, sidebarOpen, setSidebarOpen, onOpenSettings, ttsSettings }) {
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isFormCollapsed, setIsFormCollapsed] = useState(false);
  const mediaRecorderRef = useRef(null);
  const messageListRef = useRef(null);

  // Scroll to bottom when new messages appear
  useEffect(() => {
    if (messageListRef.current) {
      messageListRef.current.scrollTop = messageListRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = (e) => {
    e.preventDefault();
    onSendMessage(input, 'text');
    setInput('');
  };

  const handleVoiceInput = async () => {
    if (isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mediaRecorder = new MediaRecorder(stream);
        mediaRecorderRef.current = mediaRecorder;
        const audioChunks = [];

        mediaRecorder.addEventListener("dataavailable", event => {
          audioChunks.push(event.data);
        });

        mediaRecorder.addEventListener("stop", async () => {
          const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
          try {
            const recognizedText = await api.asr(audioBlob);
            if (recognizedText && recognizedText.trim()) {
                onSendMessage(recognizedText, 'voice');
            }
          } catch (error) {
            console.error("ASR failed:", error);
            // Optionally show an error to the user
          }
          stream.getTracks().forEach(track => track.stop()); // Stop microphone
        });

        mediaRecorder.start();
        setIsRecording(true);
      } catch (error) {
        console.error("Could not get microphone access:", error);
        // Show an error message to the user
      }
    }
  };

  return (
    <div className="chat-window">
      <div className="chat-header">
        <button className="btn btn-light me-2 btn-menu" onClick={() => setSidebarOpen(!sidebarOpen)} title={sidebarOpen ? "收起侧边栏" : "展开侧边栏"}>
            <i className={`bi ${sidebarOpen ? 'bi-layout-sidebar-inset' : 'bi-layout-sidebar'}`}></i>
        </button>
        <span className="role-name">{roleName}</span>
        <button className="btn btn-light ms-auto" onClick={onOpenSettings}>
            <i className="bi bi-gear-fill"></i>
        </button>
      </div>

      <div className="message-list" ref={messageListRef}>
        {/* 添加调试信息 */}

        {messages.filter(msg => msg.role !== 'system' && msg.role !== 'tool').map((msg, index) => (
          <Message key={`${msg.role}-${index}-${msg.content?.substring(0, 50)}`} message={msg} ttsSettings={ttsSettings} roleName={roleName} roleAlias={currentRole} />
        ))}
        {loading && (
          <div className="message assistant">
            <div className="message-avatar">
              <img src="/ai-avatar.png" alt="AI" />
              <div className="avatar-loading-spinner">
                <div className="spinner-border spinner-border-sm text-primary" role="status">
                  <span className="visually-hidden">Loading...</span>
                </div>
              </div>
            </div>
            <div className="message-content">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="chat-input-container">
        <button 
          className="btn btn-outline-secondary collapse-btn"
          type="button"
          onClick={() => setIsFormCollapsed(!isFormCollapsed)}
          title={isFormCollapsed ? "展开输入框" : "收起输入框"}
        >
          <i className={`bi ${isFormCollapsed ? 'bi-chevron-up' : 'bi-chevron-down'}`}></i>
        </button>
        
        <form className={`chat-input-form ${isFormCollapsed ? 'collapsed' : ''}`} onSubmit={handleSubmit}>
          <button 
              className={`btn voice-btn ${isRecording ? 'btn-danger' : 'btn-outline-secondary'}`} 
              type="button"
              onClick={handleVoiceInput}
              disabled={loading}
              title={isRecording ? "停止录音" : "语音输入"}
          >
              <i className={`bi ${isRecording ? 'bi-stop-fill' : 'bi-mic-fill'}`}></i>
          </button>
          
          <input
            type="text"
            className="form-control"
            placeholder={loading ? "AI正在思考中..." : "输入消息..."}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
          />
        
        {loading ? (
          <button 
            className="btn btn-outline-danger stop-btn" 
            type="button"
            onClick={onInterrupt}
            title="中断当前请求"
          >
            <i className="bi bi-stop-fill"></i>
          </button>
        ) : (
          <button 
             className="btn btn-outline-danger stop-btn" 
             type="button"
             onClick={onStopAll}
             title="停止输出/播放"
           >
             <i className="bi bi-stop-circle-fill"></i>
           </button>
        )}
        
        <button className="btn btn-primary send-btn" type="submit" disabled={!input.trim() || loading}>
            <i className="bi bi-send-fill"></i>
        </button>
      </form>
    </div>
    </div>
  );
}

export default ChatWindow;
