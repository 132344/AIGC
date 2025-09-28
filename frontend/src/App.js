import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import HomePage from './components/HomePage';
import ChatPage from './components/ChatPage';
import './App.css'; // Keep existing App.css for general styling

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/chat/:roleId" element={<ChatPage />} />
      </Routes>
    </Router>
  );
}

export default App;