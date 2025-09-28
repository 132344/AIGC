import React, { useState, useEffect } from 'react';
import api from '../services/api';

function SettingsModal({ 
    isOpen, 
    onClose, 
    roleAlias, 
    roleName, 
    autoPlay, 
    setAutoPlay, 
    prefixWithVoice, 
    setPrefixWithVoice,
    ttsSettings,
    setTtsSettings
}) {
  const [prompt, setPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [saveStatus, setSaveStatus] = useState('idle'); // idle, saving, success, error
  const [ttsOptions, setTtsOptions] = useState(null);

  useEffect(() => {
    if (isOpen) {
      if (roleAlias) {
        setIsLoading(true);
        setSaveStatus('idle'); // Reset save status when opening
        api.getRolePrompt(roleAlias)
          .then(data => setPrompt(data.prompt))
          .catch(err => {
              console.error("Failed to fetch prompt:", err);
              setPrompt("无法加载提示词。");
          })
          .finally(() => setIsLoading(false));
      }
      api.getTtsOptions()
        .then(data => setTtsOptions(data))
        .catch(err => console.error("Failed to fetch tts options:", err));
    }
  }, [isOpen, roleAlias]);

  const handleSettingChange = (e) => {
    const { name, value } = e.target;
    setTtsSettings(prev => ({ ...prev, [name]: parseFloat(value) }));
  };

  const handleSave = async () => {
    setSaveStatus('saving');
    try {
      await api.updateRolePrompt(roleAlias, prompt);
      setSaveStatus('success');
      setTimeout(() => setSaveStatus('idle'), 2000); // Reset after 2s
    } catch (error) {
      console.error("Failed to save prompt:", error);
      setSaveStatus('error');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal show d-block" tabIndex="-1" onClick={onClose}>
      <div className="modal-dialog modal-dialog-centered modal-lg" onClick={e => e.stopPropagation()}>
        <div className="modal-content">
          <div className="modal-header">
            <h5 className="modal-title">设置</h5>
            <button type="button" className="btn-close" onClick={onClose}></button>
          </div>
          <div className="modal-body">
            <div className="row">
                <div className="col-md-6">
                    <div className="mb-3">
                        <label htmlFor="system-prompt" className="form-label"><strong>{roleName}</strong> 的系统提示词</label>
                        {isLoading ? (
                            <div className="text-center"><div className="spinner-border spinner-border-sm"></div></div>
                        ) : (
                            <textarea 
                                id="system-prompt"
                                className="form-control"
                                rows="15"
                                value={prompt}
                                onChange={(e) => setPrompt(e.target.value)}
                            />
                        )}
                    </div>
                </div>
                <div className="col-md-6">
                    <h6>语音设置</h6>
                    {ttsOptions ? (
                        <>
                            <div className="mb-3">
                                <label htmlFor="tts-voice" className="form-label">音色</label>
                                <select id="tts-voice" name="voice" className="form-select" value={ttsSettings.voice} onChange={handleSettingChange}>
                                    {Object.entries(ttsOptions.voices).map(([code, name]) => (
                                        <option key={code} value={code}>{name}</option>
                                    ))}
                                </select>
                            </div>
                            <div className="mb-3">
                                <label htmlFor="tts-speed" className="form-label">语速: {ttsSettings.speed}x</label>
                                <input type="range" id="tts-speed" name="speed" className="form-range" min="-2" max="2" step="1" value={ttsSettings.speed} onChange={handleSettingChange} />
                            </div>
                            <div className="mb-3">
                                <label htmlFor="tts-volume" className="form-label">音量: {ttsSettings.volume}</label>
                                <input type="range" id="tts-volume" name="volume" className="form-range" min="-10" max="10" step="1" value={ttsSettings.volume} onChange={handleSettingChange} />
                            </div>
                        </>
                    ) : <div>加载语音选项中...</div>}
                    <hr />
                    <h6>其他设置</h6>
                    <div className="form-check form-switch">
                        <input className="form-check-input" type="checkbox" role="switch" id="auto-play-switch" checked={autoPlay} onChange={(e) => setAutoPlay(e.target.checked)} />
                        <label className="form-check-label" htmlFor="auto-play-switch">自动播放AI语音</label>
                    </div>
                    <div className="form-check form-switch mt-2">
                        <input className="form-check-input" type="checkbox" role="switch" id="prefix-voice-switch" checked={prefixWithVoice} onChange={(e) => setPrefixWithVoice(e.target.checked)} />
                        <label className="form-check-label" htmlFor="prefix-voice-switch">告知模型语音输入来源</label>
                    </div>
                </div>
            </div>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>关闭</button>
            <button type="button" className="btn btn-primary" onClick={handleSave} disabled={saveStatus === 'saving'}>
              {saveStatus === 'saving' && <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>}
              {saveStatus === 'success' && <i className="bi bi-check-circle-fill me-2"></i>}
              {saveStatus === 'error' && <i className="bi bi-exclamation-triangle-fill me-2"></i>}
              <span>
                {saveStatus === 'saving' ? '保存中...' : 
                 saveStatus === 'success' ? '已保存' : 
                 saveStatus === 'error' ? '保存失败' : '保存'}
              </span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SettingsModal;