import { useParams, Link } from 'react-router-dom'
import { getArticle } from '../articles'
import './ArticlePage.css'

function ArticlePage({ selectedModel }) {
  const { id } = useParams()

  const article = getArticle(id, selectedModel)

  if (!article) {
    return (
      <div className="article-page">
        <h1>Article not found</h1>
        <Link to="/">Back to Home</Link>
      </div>
    )
  }

  // Split content into paragraphs
  const paragraphs = article.content.split('\n').filter(p => p.trim())

  return (
    <div className="article-page">
      <Link to="/" className="back-link">← Back to Home</Link>
      <h1>{article.title}</h1>
      <img src={article.image} alt={article.title} className="article-hero-image" />

      <div className="article-score">
        <span className="score-label">Score:</span>
        <span className="score-value">{article.score}</span>
      </div>

      <div className="article-content">
        {paragraphs.map((paragraph, index) => (
          <p key={index}>{paragraph}</p>
        ))}
      </div>

      {article.review && (
        <div className="article-review">
          <h3>Review</h3>
          <p>{article.review}</p>
        </div>
      )}
    </div>
  )
}

export default ArticlePage
