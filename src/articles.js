// Import all real articles
import anthropicLongTerm from './real-articles/anthropic-long-term.json'
import anthropicRsp from './real-articles/anthropic-rsp.json'
import deepmind from './real-articles/deepmind.json'
import frontierCommittments from './real-articles/frontier-committments.json'
import openaiPreparedness from './real-articles/openai-preparedness-framework.json'
import xaiRisk from './real-articles/xai-risk-management.json'

const rawArticles = [
  { id: 'anthropic-long-term', ...anthropicLongTerm },
  { id: 'anthropic-rsp', ...anthropicRsp },
  { id: 'deepmind', ...deepmind },
  { id: 'frontier-committments', ...frontierCommittments },
  { id: 'openai-preparedness', ...openaiPreparedness },
  { id: 'xai-risk', ...xaiRisk }
]

// Transform articles to match expected format
export function getArticlesByModel(model) {
  const modelKey = model === 'gpt-3.5-turbo' ? 'gpt3.5' : 'gpt5'

  return rawArticles.map(article => ({
    id: article.id,
    title: article.title,
    image: article.photo.replace('public/', '/ai-news-verifier/'),
    content: article[modelKey]?.content || '',
    review: article[modelKey]?.review || '',
    score: article[modelKey]?.score || 0
  }))
}

export function getArticleById(id) {
  const article = rawArticles.find(a => a.id === id)
  if (!article) return null

  return {
    id: article.id,
    title: article.title,
    image: article.photo.replace('public/', '/ai-news-verifier/'),
    'gpt3.5': article['gpt3.5'],
    'gpt5': article['gpt5']
  }
}

export function getArticle(id, model) {
  const article = rawArticles.find(a => a.id === id)
  if (!article) return null

  const modelKey = model === 'gpt-3.5-turbo' ? 'gpt3.5' : 'gpt5'

  return {
    id: article.id,
    title: article.title,
    image: article.photo.replace('public/', '/ai-news-verifier/'),
    content: article[modelKey]?.content || '',
    review: article[modelKey]?.review || '',
    score: article[modelKey]?.score || 0
  }
}
