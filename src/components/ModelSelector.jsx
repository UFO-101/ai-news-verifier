import { getArticlesByModel } from '../articles'
import { useLocation } from 'react-router-dom'
import Navigation from './Navigation'
import './ModelSelector.css'

const MODEL_OPTIONS = [
  { value: 'gpt-3.5-turbo', label: 'GPT-3.5' },
  { value: 'gpt-5', label: 'GPT-5' }
]

function ModelSelector({ selectedModel, setSelectedModel }) {
  const location = useLocation()
  const showModelControls = location.pathname === '/blog' || location.pathname.startsWith('/article')
  const handleSliderChange = (e) => {
    const index = parseInt(e.target.value)
    setSelectedModel(MODEL_OPTIONS[index].value)
  }

  const currentIndex = MODEL_OPTIONS.findIndex(opt => opt.value === selectedModel)

  // Calculate average score for each model
  const modelAverages = MODEL_OPTIONS.map(model => {
    const articles = getArticlesByModel(model.value)
    const total = articles.reduce((sum, article) => sum + (article.score || 0), 0)
    return {
      model: model.label,
      average: articles.length > 0 ? total / articles.length : 0
    }
  })

  const maxAverage = Math.max(...modelAverages.map(m => m.average), 100)

  return (
    <div className="model-selector-fixed">
      <div className="model-selector-content">
        <img src="/ai-news-verifier/AI-lab-watchdog.png" alt="AI Lab Watchdog" className="header-logo" />
        <Navigation />
        <div className="left-section" style={{ visibility: showModelControls ? 'visible' : 'hidden' }}>
          <span className="model-label">Model:</span>
          <div className="slider-container">
            <span className="model-option">{MODEL_OPTIONS[0].label}</span>
            <input
              type="range"
              min="0"
              max="1"
              step="1"
              value={currentIndex}
              onChange={handleSliderChange}
              className="model-slider"
            />
            <span className="model-option">{MODEL_OPTIONS[1].label}</span>
          </div>
          <div className="current-model">{MODEL_OPTIONS[currentIndex].label}</div>
        </div>
        <div className="graph-container" style={{ visibility: showModelControls ? 'visible' : 'hidden' }}>
          <svg className="line-graph" viewBox="0 0 300 80" preserveAspectRatio="xMidYMid meet">
          {/* Grid lines */}
          <line x1="30" y1="10" x2="30" y2="55" stroke="#ccc" strokeWidth="0.5" />
          <line x1="30" y1="55" x2="270" y2="55" stroke="#ccc" strokeWidth="0.5" />

          {/* Y-axis labels */}
          <text x="25" y="13" fontSize="7" fill="currentColor" textAnchor="end">{maxAverage.toFixed(1)}</text>
          <text x="25" y="56" fontSize="7" fill="currentColor" textAnchor="end">0</text>

          {/* Line connecting points */}
          <polyline
            points={modelAverages.map((data, i) => {
              const x = 30 + (i * 120)
              const y = 55 - (data.average / (maxAverage || 1)) * 45
              return `${x},${y}`
            }).join(' ')}
            fill="none"
            stroke="#646cff"
            strokeWidth="2"
          />

          {/* Data points and labels */}
          {modelAverages.map((data, i) => {
            const x = 30 + (i * 120)
            const y = 55 - (data.average / (maxAverage || 1)) * 45
            const isSelected = i === currentIndex

            return (
              <g key={i}>
                {isSelected && (
                  <circle
                    cx={x}
                    cy={y}
                    r="8"
                    fill={data.average === 0 ? "#4caf50" : "#646cff"}
                    opacity="0.3"
                  />
                )}
                <circle
                  cx={x}
                  cy={y}
                  r={isSelected ? "5" : "2.5"}
                  fill={data.average === 0 ? "#4caf50" : "#646cff"}
                  stroke="white"
                  strokeWidth={isSelected ? "2" : "1"}
                />
                <text
                  x={x}
                  y="68"
                  fontSize="8"
                  fill="currentColor"
                  textAnchor="middle"
                  fontWeight={isSelected ? "bold" : "normal"}
                >
                  {data.model}
                </text>
                <text
                  x={x}
                  y={y - 6}
                  fontSize="8"
                  fill="currentColor"
                  textAnchor="middle"
                  fontWeight="bold"
                >
                  {data.average.toFixed(1)}
                </text>
              </g>
            )
          })}
        </svg>
        </div>
      </div>
    </div>
  )
}

export default ModelSelector
