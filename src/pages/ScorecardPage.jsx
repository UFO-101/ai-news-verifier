import { useState } from 'react'
import humanScores from '../scorecard/official_scores.json'
import openaiScores from '../scorecard/real-ai-generated-scores/ai-gen-openai-scores.json'
import deepmindScores from '../scorecard/real-ai-generated-scores/ai-gen-deepmind-scores.json'
import anthropicScores from '../scorecard/real-ai-generated-scores/ai-gen-anthropic-scores.json'
import metaScores from '../scorecard/real-ai-generated-scores/ai-gen-meta-scores.json'
import xaiScores from '../scorecard/real-ai-generated-scores/ai-gen-xai-scores.json'
import microsoftScores from '../scorecard/real-ai-generated-scores/ai-gen-microsoft-scores.json'
import deepseekScores from '../scorecard/real-ai-generated-scores/ai-gen-deepseek.json'
import './ScorecardPage.css'

function ScorecardPage() {
  const [hoveredPoint, setHoveredPoint] = useState(null)
  const [hoveredOverallPoint, setHoveredOverallPoint] = useState(null)
  const [hoveredCell, setHoveredCell] = useState(null)
  // Extract company names from the first subcategory
  const companies = Object.keys(humanScores[0].subcategories[0].scores)

  // Map company names to their AI-generated score data
  // Normalize data structure - some files have {categories: [...]} and others are just [...]
  const companyScoreMap = {
    'OpenAI': openaiScores,
    'DeepMind': deepmindScores,
    'Anthropic': anthropicScores,
    'Meta': { categories: metaScores },
    'xAI': xaiScores,
    'Microsoft': microsoftScores,
    'DeepSeek': deepseekScores
  }

  // Build AI scores structure from human scores template
  const aiScores = humanScores.map((category, catIndex) => {
    return {
      ...category,
      subcategories: category.subcategories.map((subcategory, subIndex) => {
        const newScores = {}
        const reasoning = {}

        // For each company, try to get real scores and reasoning
        companies.forEach(company => {
          const companyData = companyScoreMap[company]
          const companyCategory = companyData?.categories?.[catIndex]
          const companySubcategory = companyCategory?.subcategories?.[subIndex]

          // Use real score if available, otherwise default to 0
          newScores[company] = companySubcategory?.scores?.[company] ?? 0

          // Get reasoning from either 'reasoning' or 'description' field
          const reasoningText = companySubcategory?.reasoning || companySubcategory?.description
          if (reasoningText && reasoningText !== '*model reasoning*') {
            reasoning[company] = reasoningText
          }
        })

        return {
          ...subcategory,
          scores: newScores,
          reasoning: reasoning
        }
      })
    }
  })

  // Calculate weighted scores for each company
  const calculateWeightedScore = (company, data) => {
    let totalWeightedScore = 0
    let totalWeight = 0

    data.forEach(category => {
      category.subcategories.forEach(subcategory => {
        const score = subcategory.scores[company] || 0
        const weight = (category.weight / 100) * (subcategory.weight / 100)
        totalWeightedScore += score * weight
        totalWeight += weight
      })
    })

    return Math.round(totalWeightedScore / totalWeight)
  }

  const renderLabels = (data) => (
    <div className="labels-section">
      <h2 className="heatmap-title" style={{ visibility: 'hidden' }}>Labels</h2>
      <div className="labels-container">
        {/* Header spacer */}
        <div className="label-header"></div>

        {/* Weighted score label */}
        <div className="label-row label-weighted">
          <div className="category-label">Weighted score</div>
          <div className="subcategory-label"></div>
        </div>

        {/* Category and subcategory labels */}
        {data.map((category, catIndex) => (
          <>
            {category.subcategories.map((subcategory, subIndex) => (
              <div key={`${catIndex}-${subIndex}`} className="label-row">
                {subIndex === 0 ? (
                  <div className="category-label category-label-group" style={{ gridRow: `span ${category.subcategories.length}` }}>
                    {category.category}
                  </div>
                ) : null}
                <div className="subcategory-label">
                  {subcategory.name}
                </div>
              </div>
            ))}
          </>
        ))}
      </div>
    </div>
  )

  const renderHeatmap = (data, title, showReasoning = false) => (
    <div className="heatmap-section">
      <h2 className="heatmap-title">{title}</h2>
      <div className="scorecard-container-scores">
        {/* Header row with company logos */}
        {companies.map(company => (
          <div key={company} className="company-header">
            <img src={logoMap[company]} alt={company} className="company-logo" />
          </div>
        ))}

        {/* Weighted score row */}
        {companies.map(company => {
          const weightedScore = calculateWeightedScore(company, data)
          return (
            <div
              key={company}
              className="score-cell weighted-score-cell"
              style={{ backgroundColor: getScoreColor(weightedScore) }}
            >
              {weightedScore}%
            </div>
          )
        })}

        {/* Categories and subcategories */}
        {data.map((category, catIndex) => (
          <>
            {category.subcategories.map((subcategory, subIndex) => (
              <>
                {companies.map(company => {
                  const score = subcategory.scores[company]
                  const cellKey = `${catIndex}-${subIndex}-${company}`
                  const reasoning = showReasoning && subcategory.reasoning?.[company]
                  const hasReasoning = !!reasoning
                  return (
                    <div
                      key={company}
                      className="score-cell"
                      style={{
                        backgroundColor: getScoreColor(score),
                        cursor: hasReasoning ? 'pointer' : 'default'
                      }}
                      onMouseEnter={(e) => {
                        if (hasReasoning) {
                          const rect = e.currentTarget.getBoundingClientRect()
                          setHoveredCell({
                            key: cellKey,
                            reasoning: reasoning,
                            x: rect.left + rect.width / 2,
                            y: rect.top
                          })
                        }
                      }}
                      onMouseLeave={() => hasReasoning && setHoveredCell(null)}
                    >
                      {score}%
                    </div>
                  )
                })}
              </>
            ))}
          </>
        ))}
      </div>
    </div>
  )

  // Get color for score value
  const getScoreColor = (score) => {
    if (score === 0) return '#f5cac3' // light coral
    if (score <= 10) return '#f5b5a8'
    if (score <= 20) return '#f29f8d'
    if (score <= 30) return '#e88971'
    if (score <= 40) return '#de7356'
    if (score <= 50) return '#c9986d'
    if (score <= 60) return '#b4a982'
    if (score <= 70) return '#9fb897'
    if (score <= 80) return '#8ac7ac'
    return '#75d5c1' // teal for high scores
  }

  // Logo mapping
  const logoMap = {
    'Anthropic': '/ai-news-verifier/logos/anthropic.svg',
    'DeepMind': '/ai-news-verifier/logos/DeepMind_new_logo.svg',
    'OpenAI': '/ai-news-verifier/logos/openai.svg',
    'Meta': '/ai-news-verifier/logos/meta.svg',
    'xAI': '/ai-news-verifier/logos/XAI_Logo.svg',
    'Microsoft': '/ai-news-verifier/logos/microsoft.svg',
    'DeepSeek': '/ai-news-verifier/logos/deepseek-logo-icon.svg'
  }

  // Collect all score pairs for scatterplot
  const getScatterData = () => {
    const points = []
    humanScores.forEach((category, catIndex) => {
      category.subcategories.forEach((subcategory, subIndex) => {
        companies.forEach(company => {
          const humanScore = subcategory.scores[company]
          const aiScore = aiScores[catIndex].subcategories[subIndex].scores[company]
          points.push({
            human: humanScore,
            ai: aiScore,
            company,
            subcategory: subcategory.name
          })
        })
      })
    })
    return points
  }

  const scatterData = getScatterData()

  // Get overall scores for second scatterplot
  const getOverallScores = () => {
    const points = []
    companies.forEach(company => {
      const humanOverall = calculateWeightedScore(company, humanScores)

      // Get AI overall score from the JSON file
      const companyData = companyScoreMap[company]
      const aiOverall = companyData?.overall?.[company] ?? calculateWeightedScore(company, aiScores)

      points.push({
        human: humanOverall,
        ai: aiOverall,
        company
      })
    })
    return points
  }

  const overallScatterData = getOverallScores()

  // Calculate Pearson correlation coefficient
  const calculateCorrelation = (data) => {
    const n = data.length
    const sumX = data.reduce((sum, p) => sum + p.human, 0)
    const sumY = data.reduce((sum, p) => sum + p.ai, 0)
    const sumXY = data.reduce((sum, p) => sum + p.human * p.ai, 0)
    const sumX2 = data.reduce((sum, p) => sum + p.human * p.human, 0)
    const sumY2 = data.reduce((sum, p) => sum + p.ai * p.ai, 0)

    const numerator = n * sumXY - sumX * sumY
    const denominator = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY))

    return numerator / denominator
  }

  const correlation = calculateCorrelation(scatterData)
  const overallCorrelation = calculateCorrelation(overallScatterData)

  return (
    <div className="scorecard-page">
      <div className="heatmaps-wrapper">
        {renderLabels(humanScores)}
        {renderHeatmap(humanScores, 'Human Researchers', false)}
        <div>
          {renderHeatmap(aiScores, 'AI Analysis', true)}
        </div>
      </div>

      {hoveredCell && (
        <div
          className="reasoning-tooltip"
          style={{
            position: 'fixed',
            left: `${hoveredCell.x}px`,
            top: `${hoveredCell.y - 10}px`,
            transform: 'translate(-50%, -100%)'
          }}
        >
          <div className="reasoning-content">
            {hoveredCell.reasoning}
          </div>
        </div>
      )}

      <div className="scatterplot-section">
        <h2 className="scatterplot-title">Human vs AI Scores Comparison</h2>
        <div className="scatterplot-wrapper">
          <div className="scatterplot-container">
            <svg className="scatterplot" viewBox="0 0 600 500">
              {/* Axes */}
              <line x1="60" y1="440" x2="560" y2="440" stroke="#666" strokeWidth="2" />
              <line x1="60" y1="40" x2="60" y2="440" stroke="#666" strokeWidth="2" />

              {/* Grid lines */}
              {[0, 25, 50, 75, 100].map(val => {
                const x = 60 + (val / 100) * 500
                const y = 440 - (val / 100) * 400
                return (
                  <g key={val}>
                    <line x1={x} y1="440" x2={x} y2="435" stroke="#666" strokeWidth="1" />
                    <line x1="60" y1={y} x2="65" y2={y} stroke="#666" strokeWidth="1" />
                    <line x1={x} y1="440" x2={x} y2="40" stroke="#e0e0e0" strokeWidth="0.5" opacity="0.5" />
                    <line x1="60" y1={y} x2="560" y2={y} stroke="#e0e0e0" strokeWidth="0.5" opacity="0.5" />
                    <text x={x} y="455" fontSize="12" fill="#666" textAnchor="middle">{val}</text>
                    <text x="45" y={y + 4} fontSize="12" fill="#666" textAnchor="end">{val}</text>
                  </g>
                )
              })}

              {/* Diagonal reference line (y=x) */}
              <line x1="60" y1="440" x2="560" y2="40" stroke="#999" strokeWidth="1" strokeDasharray="5,5" opacity="0.5" />

              {/* Data points */}
              {scatterData.map((point, i) => {
                const x = 60 + (point.human / 100) * 500
                const y = 440 - (point.ai / 100) * 400
                return (
                  <circle
                    key={i}
                    cx={x}
                    cy={y}
                    r="4"
                    fill="#646cff"
                    opacity={hoveredPoint === i ? "1" : "0.6"}
                    stroke={hoveredPoint === i ? "#333" : "none"}
                    strokeWidth="2"
                    style={{ cursor: 'pointer' }}
                    onMouseEnter={() => setHoveredPoint(i)}
                    onMouseLeave={() => setHoveredPoint(null)}
                  />
                )
              })}

              {/* Axis labels */}
              <text x="310" y="485" fontSize="14" fill="#333" textAnchor="middle" fontWeight="600">Human Researcher Score (%)</text>
              <text x="20" y="240" fontSize="14" fill="#333" textAnchor="middle" fontWeight="600" transform="rotate(-90 20 240)">AI Analysis Score (%)</text>
            </svg>

            {hoveredPoint !== null && (
              <div className="scatter-tooltip">
                <div className="tooltip-company">{scatterData[hoveredPoint].company}</div>
                <div className="tooltip-subcategory">{scatterData[hoveredPoint].subcategory}</div>
                <div className="tooltip-scores">
                  <div>Human: <strong>{scatterData[hoveredPoint].human}%</strong></div>
                  <div>AI: <strong>{scatterData[hoveredPoint].ai}%</strong></div>
                </div>
              </div>
            )}
          </div>

          <div className="correlation-display">
            <div className="correlation-label">Correlation</div>
            <div className="correlation-value">{correlation.toFixed(3)}</div>
          </div>
        </div>
      </div>

      <div className="scatterplot-section">
        <h2 className="scatterplot-title">Overall Scores Comparison</h2>
        <div className="scatterplot-wrapper">
          <div className="scatterplot-container">
            <svg className="scatterplot" viewBox="0 0 600 500">
              {/* Axes */}
              <line x1="60" y1="440" x2="560" y2="440" stroke="#666" strokeWidth="2" />
              <line x1="60" y1="40" x2="60" y2="440" stroke="#666" strokeWidth="2" />

              {/* Grid lines */}
              {[0, 25, 50, 75, 100].map(val => {
                const x = 60 + (val / 100) * 500
                const y = 440 - (val / 100) * 400
                return (
                  <g key={val}>
                    <line x1={x} y1="440" x2={x} y2="435" stroke="#666" strokeWidth="1" />
                    <line x1="60" y1={y} x2="65" y2={y} stroke="#666" strokeWidth="1" />
                    <line x1={x} y1="440" x2={x} y2="40" stroke="#e0e0e0" strokeWidth="0.5" opacity="0.5" />
                    <line x1="60" y1={y} x2="560" y2={y} stroke="#e0e0e0" strokeWidth="0.5" opacity="0.5" />
                    <text x={x} y="455" fontSize="12" fill="#666" textAnchor="middle">{val}</text>
                    <text x="45" y={y + 4} fontSize="12" fill="#666" textAnchor="end">{val}</text>
                  </g>
                )
              })}

              {/* Diagonal reference line (y=x) */}
              <line x1="60" y1="440" x2="560" y2="40" stroke="#999" strokeWidth="1" strokeDasharray="5,5" opacity="0.5" />

              {/* Data points */}
              {overallScatterData.map((point, i) => {
                const x = 60 + (point.human / 100) * 500
                const y = 440 - (point.ai / 100) * 400
                return (
                  <circle
                    key={i}
                    cx={x}
                    cy={y}
                    r="6"
                    fill="#646cff"
                    opacity={hoveredOverallPoint === i ? "1" : "0.6"}
                    stroke={hoveredOverallPoint === i ? "#333" : "none"}
                    strokeWidth="2"
                    style={{ cursor: 'pointer' }}
                    onMouseEnter={() => setHoveredOverallPoint(i)}
                    onMouseLeave={() => setHoveredOverallPoint(null)}
                  />
                )
              })}

              {/* Axis labels */}
              <text x="310" y="485" fontSize="14" fill="#333" textAnchor="middle" fontWeight="600">Human Researcher Overall Score (%)</text>
              <text x="20" y="240" fontSize="14" fill="#333" textAnchor="middle" fontWeight="600" transform="rotate(-90 20 240)">AI Analysis Overall Score (%)</text>
            </svg>

            {hoveredOverallPoint !== null && (
              <div className="scatter-tooltip">
                <div className="tooltip-company">{overallScatterData[hoveredOverallPoint].company}</div>
                <div className="tooltip-scores">
                  <div>Human: <strong>{overallScatterData[hoveredOverallPoint].human}%</strong></div>
                  <div>AI: <strong>{overallScatterData[hoveredOverallPoint].ai}%</strong></div>
                </div>
              </div>
            )}
          </div>

          <div className="correlation-display">
            <div className="correlation-label">Correlation</div>
            <div className="correlation-value">{overallCorrelation.toFixed(3)}</div>
          </div>
        </div>
      </div>

    </div>
  )
}

export default ScorecardPage
