import { Link } from 'react-router-dom'
import { getArticlesByModel } from '../articles'
import './HomePage.css'

function HomePage({ selectedModel }) {
  const articles = getArticlesByModel(selectedModel)

  // Calculate average score
  const totalScore = articles.reduce((sum, article) => {
    return sum + (article.score || 0)
  }, 0)
  const averageScore = articles.length > 0 ? (totalScore / articles.length).toFixed(1) : 0

  return (
    <div className="home-page">
      <div className="header">
        <img src="/ai-news-verifier/AI-lab-watchdog.png" alt="AI Lab Watchdog Logo" className="logo" />
      </div>

      <div className="average-score">
        <span className="score-label">Average Score:</span>
        <span className={`score-value ${averageScore === '100.0' ? 'perfect-score' : ''}`}>
          {averageScore}
        </span>
      </div>

      <div className="articles-list">
        {articles.map(article => {
          const score = article.score || 0
          let badgeClass = 'misinfo-badge'
          if (score === 100) {
            badgeClass += ' no-misinfo'
          } else if (score >= 75) {
            badgeClass += ' good-score'
          } else if (score >= 50) {
            badgeClass += ' medium-score'
          } else {
            badgeClass += ' low-score'
          }

          return (
            <Link
              key={article.id}
              to={`/article/${article.id}`}
              className="article-card"
            >
              <img src={article.image} alt={article.title} className="article-image" />
              <div className={badgeClass}>
                {score}
              </div>
              <h2>{article.title}</h2>
            </Link>
          )
        })}
      </div>
    </div>
  )
}

export default HomePage
