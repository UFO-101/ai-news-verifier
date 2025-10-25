import { useState } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import HomePage from './pages/HomePage'
import ArticlePage from './pages/ArticlePage'
import ScorecardPage from './pages/ScorecardPage'
import ModelSelector from './components/ModelSelector'
import './App.css'

function App() {
  const [selectedModel, setSelectedModel] = useState('gpt-3.5-turbo')

  return (
    <Router basename="/ai-news-verifier">
      <ModelSelector selectedModel={selectedModel} setSelectedModel={setSelectedModel} />
      <Routes>
        <Route path="/" element={<Navigate to="/blog" replace />} />
        <Route path="/blog" element={<HomePage selectedModel={selectedModel} />} />
        <Route path="/article/:id" element={<ArticlePage selectedModel={selectedModel} />} />
        <Route path="/scorecard" element={<ScorecardPage />} />
      </Routes>
    </Router>
  )
}

export default App
