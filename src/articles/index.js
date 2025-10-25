import trumpArticle from './trump.json'
import biotechArticle from './biotech.json'
import borisJohnsonArticle from './boris-johnson.json'
import britneyArticle from './britney-spears.json'
import fdaArticle from './fda.json'
import healthTechArticle from './health-tech.json'
import jimmyFallonArticle from './jimmy-fallon.json'
import kierStarmerArticle from './kier-starmer.json'
import openaiArticle from './openai-sam-altman.json'
import supremeCourtArticle from './supreme-court.json'
import tedCruzArticle from './ted-cruz.json'

// Article data with model versions
export const articlesData = {
  'trump': {
    ...trumpArticle,
    image: '/ai-news-verifier/trump.jpg'
  },
  'biotech': {
    ...biotechArticle,
    image: '/ai-news-verifier/biotech.webp'
  },
  'boris-johnson': {
    ...borisJohnsonArticle,
    image: '/ai-news-verifier/boris-johnson.webp'
  },
  'britney-spears': {
    ...britneyArticle,
    image: '/ai-news-verifier/britney_spears.webp'
  },
  'fda': {
    ...fdaArticle,
    image: '/ai-news-verifier/FDA.jpg'
  },
  'health-tech': {
    ...healthTechArticle,
    image: '/ai-news-verifier/health_tech.jpeg'
  },
  'jimmy-fallon': {
    ...jimmyFallonArticle,
    image: '/ai-news-verifier/Jimmy-Fallon.webp'
  },
  'kier-starmer': {
    ...kierStarmerArticle,
    image: '/ai-news-verifier/kier_starmer.jpg'
  },
  'openai-sam-altman': {
    ...openaiArticle,
    image: '/ai-news-verifier/openai_sam_altman.jpg'
  },
  'supreme-court': {
    ...supremeCourtArticle,
    image: '/ai-news-verifier/supreme_court.jpg'
  },
  'ted-cruz': {
    ...tedCruzArticle,
    image: '/ai-news-verifier/ted_cruz.jpg'
  }
}

// Get articles for a specific model
export const getArticlesByModel = (model = 'gpt3') => {
  return Object.keys(articlesData).map(id => ({
    id,
    title: articlesData[id].title,
    content: articlesData[id][model]?.content || articlesData[id].gpt3.content,
    image: articlesData[id].image
  }))
}

// Get single article by ID and model
export const getArticle = (id, model = 'gpt3') => {
  const article = articlesData[id]
  if (!article) return null

  return {
    id,
    title: article.title,
    content: article[model]?.content || article.gpt3.content,
    image: article.image
  }
}
