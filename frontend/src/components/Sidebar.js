import React, { useState, useEffect } from 'react';
import api from '../services/api';

function Sidebar({
    roles,
    currentRole,
    setCurrentRole,
    contexts,
    currentContext,
    setCurrentContext,
    onNewContext,
    onDeleteContext,
    onEditContext,
    isOpen
}) {
  const [editingContext, setEditingContext] = useState(null);
  const [newContextName, setNewContextName] = useState('');
  const [roleImageUrl, setRoleImageUrl] = useState(null);

  // 获取当前角色的图片
  useEffect(() => {
    let currentImageUrl = null;
    
    const fetchRoleImage = async () => {
      if (currentRole) {
        try {
          const imageUrl = await api.getRoleImage(currentRole);
          currentImageUrl = imageUrl;
          setRoleImageUrl(imageUrl);
        } catch (error) {
          console.error('Failed to fetch role image:', error);
          setRoleImageUrl(null);
        }
      } else {
        setRoleImageUrl(null);
      }
    };

    fetchRoleImage();

    // 清理函数
    return () => {
      if (currentImageUrl) {
        URL.revokeObjectURL(currentImageUrl);
      }
    };
  }, [currentRole]);

  const handleEditClick = (e, context) => {
    e.stopPropagation();
    setEditingContext(context);
    setNewContextName(context);
  };

  const handleSaveEdit = async (oldContextName) => {
    if (newContextName.trim() && newContextName !== oldContextName) {
      await onEditContext(oldContextName, newContextName);
    }
    setEditingContext(null);
    setNewContextName('');
  };

  const handleKeyDown = (e, oldContextName) => {
    if (e.key === 'Enter') {
      handleSaveEdit(oldContextName);
    } else if (e.key === 'Escape') {
      setEditingContext(null);
      setNewContextName('');
    }
  };

  return (
    <div className={`sidebar ${isOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
            AI 角色
        </div>

        <div className="mb-3">
            <div className="mb-2">
                <label htmlFor="role-display" className="form-label mb-0">当前角色</label>
            </div>
            <div className="role-display-container">
                {roleImageUrl && (
                    <div className="role-image-container">
                        <img 
                            src={roleImageUrl} 
                            alt="角色头像" 
                            className="role-image"
                            onError={() => setRoleImageUrl(null)}
                        />
                    </div>
                )}
                <div id="role-display" className="form-control-plaintext role-name" translate="no">
                    {roles.find(r => r.id === currentRole)?.name || '未选择'}
                </div>
            </div>
        </div>

        <hr />

        <div className="d-flex justify-content-between align-items-center mb-2">
            <h6 className="mb-0">聊天历史</h6>
            <button className="btn btn-primary btn-sm" onClick={onNewContext}>新建</button>
        </div>

        <ul className="context-list">
            {contexts.map(context => (
                <li
                    key={context}
                    className={`context-item ${context === currentContext ? 'active' : ''}`}
                    onClick={() => setCurrentContext(context)}
                >
                    <div className="context-item-content">
                        {editingContext === context ? (
                            <input
                                type="text"
                                className="form-control form-control-sm"
                                value={newContextName}
                                onChange={(e) => setNewContextName(e.target.value)}
                                onBlur={() => handleSaveEdit(context)}
                                onKeyDown={(e) => handleKeyDown(e, context)}
                                autoFocus
                                style={{ minWidth: '150px' }}
                            />
                        ) : (
                            <>
                                <span className="context-name">{context}</span>
                                <button
                                    className="btn btn-sm btn-light ms-2"
                                    onClick={(e) => handleEditClick(e, context)}
                                    title="编辑上下文名称"
                                >
                                    <i className="bi bi-pencil"></i>
                                </button>
                            </>
                        )}
                    </div>
                    <button
                        className="btn-close ms-auto"
                        aria-label="Delete"
                        onClick={(e) => { e.stopPropagation(); onDeleteContext(context); }}
                    ></button>
                </li>
            ))}
        </ul>
    </div>
  );
}

export default Sidebar;
