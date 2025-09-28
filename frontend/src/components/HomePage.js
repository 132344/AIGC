import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api'; // Import the API service
import './HomePage.css';

function HomePage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [roles, setRoles] = useState({}); // State to store fetched roles
  const [loading, setLoading] = useState(true); // Loading state

  useEffect(() => {
    api.getRoles()
      .then(fetchedRoles => {
        setRoles(fetchedRoles);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch roles:", err);
        setLoading(false);
      });
  }, []); // Empty dependency array means this runs once on mount

  const filteredRoles = Object.values(roles).filter(role =>
    role.name && role.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="homepage-container">
      <header className="homepage-header">
        <h1>欢迎来到AI角色中心</h1>
        <div className="search-bar">
          <input
            type="text"
            placeholder="搜索角色..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </header>
      <main className="role-list-container">
        {loading ? (
          <p>正在加载角色...</p>
        ) : filteredRoles.length > 0 ? (
          <div className="role-grid">
            {filteredRoles.map(role => (
              <Link to={`/chat/${role.id}`} key={role.id} className="role-card">
                <h2>{role.name}</h2>
                <p>点击进入 {role.name} 聊天</p>
              </Link>
            ))}
          </div>
        ) : (
          <p>没有找到匹配的角色。</p>
        )}
      </main>
      <footer className="homepage-footer">
        <p>&copy; 2025 AIGC</p>
        <p>
          <a href="https://github.com/132344/AIGC/tree/master" target="_blank" rel="noopener noreferrer">
            <i className="bi bi-github"></i> GitHub 仓库
          </a>
        </p>
      </footer>
    </div>
  );
}

export default HomePage;
