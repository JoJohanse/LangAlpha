import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, ExternalLink, Loader2, Sparkles } from 'lucide-react';
import { getNewsArticle, askNewsArticle } from '../Dashboard/utils/api';
import { useFormatTime } from '@/hooks/useFormatTime';

interface ArticleSentiment {
  ticker: string;
  sentiment?: string;
  reasoning?: string;
}

interface ArticleSource {
  name?: string;
  favicon_url?: string;
}

// TODO: type properly once backend API schema is formalized
interface NewsArticle {
  title: string;
  published_at?: string;
  author?: string;
  source?: ArticleSource;
  tickers?: string[];
  image_url?: string;
  description?: string;
  sentiments?: ArticleSentiment[];
  article_url?: string;
  sector?: string | null;
  topic?: string | null;
  region?: string | null;
  tags?: string[];
}

function NewsDetailPage() {
  const formatTime = useFormatTime();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [article, setArticle] = useState<NewsArticle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [askLoading, setAskLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    getNewsArticle(id!)
      .then((data) => { if (!cancelled) setArticle(data as unknown as NewsArticle); })
      .catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [id]);

  const handleBack = () => navigate('/dashboard');

  const handleAskAI = async () => {
    if (!id || askLoading) return;
    setAskLoading(true);
    try {
      const payload = await askNewsArticle(id) as { thread_initial_message?: string; additional_context?: Record<string, unknown>[] };
      navigate('/chat', {
        state: {
          initialMessage: payload.thread_initial_message || (article?.title ? `Please analyze this market news and potential impact: ${article.title}` : ''),
          additionalContext: payload.additional_context || null,
        },
      });
    } catch {
      if (article?.title) {
        navigate('/chat', {
          state: {
            initialMessage: `Please analyze this market news and potential impact: ${article.title}`,
          },
        });
      }
    } finally {
      setAskLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-8" style={{ color: 'var(--color-text-secondary)' }}>
        <Loader2 className="w-6 h-6 animate-spin" />
        <p>Loading article...</p>
      </div>
    );
  }

  if (error || !article) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-8" style={{ color: 'var(--color-text-secondary)' }}>
        <p>Article not found.</p>
        <button
          onClick={handleBack}
          className="flex items-center gap-2 px-4 py-2 rounded-md cursor-pointer transition-colors"
          style={{ backgroundColor: 'var(--color-bg-card)', color: 'var(--color-text-primary)', border: '1px solid var(--color-border-default)' }}
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Dashboard
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6 max-w-4xl mx-auto" style={{ color: 'var(--color-text-primary)' }}>
      {/* Nav row */}
      <div className="flex items-center justify-between gap-2">
        <button
          onClick={handleBack}
          className="flex items-center gap-2 px-3 py-1.5 rounded-md cursor-pointer transition-colors"
          style={{ backgroundColor: 'var(--color-bg-card)', border: '1px solid var(--color-border-default)', color: 'var(--color-text-primary)' }}
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm">Back</span>
        </button>
        <button
          onClick={handleAskAI}
          disabled={askLoading}
          className="flex items-center gap-2 px-4 py-1.5 rounded-md text-sm font-medium transition-colors disabled:opacity-50"
          style={{ backgroundColor: 'var(--color-accent-primary)', color: '#fff' }}
        >
          <Sparkles className="w-4 h-4" />
          {askLoading ? 'Loading...' : 'Ask AI'}
        </button>
      </div>

      {/* Title & metadata */}
      <div className="flex flex-col gap-3">
        <h1 className="text-2xl font-bold" style={{ lineHeight: '1.3' }}>
          {article.title}
        </h1>
        <div className="flex items-center gap-3 flex-wrap">
          {article.published_at && (
            <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              {formatTime(article.published_at)}
            </span>
          )}
          {article.author && (
            <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              By {article.author}
            </span>
          )}
          {article.source?.name && (
            <span
              className="inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-md font-medium"
              style={{ backgroundColor: 'var(--color-bg-tag)', color: 'var(--color-text-primary)' }}
            >
              {article.source.favicon_url && (
                <img
                  src={article.source.favicon_url}
                  alt=""
                  className="w-3.5 h-3.5"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                />
              )}
              {article.source.name}
            </span>
          )}
        </div>

        {/* Classification */}
        {(article.sector || article.topic || article.region || (article.tags?.length ?? 0) > 0) && (
          <div className="flex items-center gap-1.5 flex-wrap">
            {article.sector && (
              <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ backgroundColor: 'var(--color-accent-soft)', color: 'var(--color-accent-light)' }}>
                {article.sector}
              </span>
            )}
            {article.topic && (
              <span className="text-xs px-2 py-0.5 rounded-full" style={{ backgroundColor: 'var(--color-bg-tag)', color: 'var(--color-text-secondary)' }}>
                {article.topic}
              </span>
            )}
            {article.region && (
              <span className="text-xs px-2 py-0.5 rounded-full" style={{ backgroundColor: 'var(--color-bg-tag)', color: 'var(--color-text-tertiary)' }}>
                {article.region}
              </span>
            )}
            {article.tags?.map((tag, i) => (
              <span key={i} className="text-xs px-2 py-0.5 rounded-full" style={{ backgroundColor: 'var(--color-bg-tag)', color: 'var(--color-text-secondary)' }}>
                #{tag}
              </span>
            ))}
          </div>
        )}

        {/* Tickers */}
        {article.tickers && article.tickers.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap">
            {article.tickers.map((ticker) => (
              <span
                key={ticker}
                className="text-xs px-2 py-0.5 rounded-full font-mono font-medium"
                style={{ backgroundColor: 'var(--color-bg-tag)', color: 'var(--color-accent-primary)' }}
              >
                {ticker}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Image */}
      {article.image_url && (
        <div className="rounded-md overflow-hidden" style={{ border: '1px solid var(--color-border-default)' }}>
          <img
            src={article.image_url}
            alt=""
            className="w-full"
            style={{ maxHeight: '400px', objectFit: 'cover' }}
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
          />
        </div>
      )}

      {/* Description */}
      {article.description && (
        <div className="rounded-md p-4" style={{ backgroundColor: 'var(--color-bg-card)', border: '1px solid var(--color-border-default)' }}>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--color-text-secondary)', lineHeight: '1.7' }}>
            {article.description}
          </p>
        </div>
      )}

      {/* Sentiments */}
      {article.sentiments && article.sentiments.length > 0 && (
        <div className="flex flex-col gap-3" style={{ borderTop: '1px solid var(--color-border-default)', paddingTop: '20px' }}>
          <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>Sentiment Analysis</h3>
          <div className="flex flex-col gap-2">
            {article.sentiments.map((s, i) => (
              <div key={i} className="flex items-start gap-3 text-xs rounded-md p-2.5" style={{ backgroundColor: 'var(--color-bg-card)', border: '1px solid var(--color-border-muted)' }}>
                <span
                  className="flex-shrink-0 font-mono font-medium px-1.5 py-0.5 rounded"
                  style={{ color: 'var(--color-accent-primary)', backgroundColor: 'var(--color-bg-tag)' }}
                >
                  {s.ticker}
                </span>
                {s.sentiment && (
                  <span
                    className="flex-shrink-0 font-medium px-1.5 py-0.5 rounded"
                    style={{
                      color: s.sentiment === 'positive' ? 'var(--color-positive)' : s.sentiment === 'negative' ? 'var(--color-negative)' : 'var(--color-text-secondary)',
                      backgroundColor: 'var(--color-bg-tag)',
                    }}
                  >
                    {s.sentiment}
                  </span>
                )}
                {s.reasoning && (
                  <span style={{ color: 'var(--color-text-secondary)' }}>{s.reasoning}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Read Full Article */}
      {article.article_url && (
        <div style={{ borderTop: '1px solid var(--color-border-default)', paddingTop: '16px', marginTop: '8px' }}>
          <a
            href={article.article_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors hover:opacity-90"
            style={{ backgroundColor: 'var(--color-accent-primary)', color: 'var(--color-text-on-accent)' }}
          >
            Read Full Article
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
      )}
    </div>
  );
}

export default NewsDetailPage;
