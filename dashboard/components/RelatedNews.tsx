"use client";

import { useEffect, useState } from "react";
import { ExternalLink, Newspaper } from "lucide-react";

interface NewsArticle {
  source: {
    id: string | null;
    name: string;
  };
  author: string | null;
  title: string;
  description: string | null;
  url: string;
  urlToImage: string | null;
  publishedAt: string;
  content: string | null;
}

interface RelatedNewsProps {
  marketName: string;
}

export function RelatedNews({ marketName }: RelatedNewsProps) {
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchNews = async () => {
      setLoading(true);
      setError(null);

      try {
        if (!marketName.trim()) {
          setArticles([]);
          setLoading(false);
          return;
        }

        // Pass raw market name - server uses OpenAI to extract search terms
        const response = await fetch(
          `/api/news?market=${encodeURIComponent(marketName)}`
        );

        if (!response.ok) {
          throw new Error(`Failed to fetch news: ${response.status}`);
        }

        const data = await response.json();

        if (data.status === "ok") {
          // Filter out articles without images for better visual consistency
          const articlesWithImages = data.articles.filter(
            (article: NewsArticle) => article.urlToImage && article.title !== "[Removed]"
          );
          setArticles(articlesWithImages.slice(0, 4));
        } else {
          setError(data.message || "Failed to fetch news");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch news");
      } finally {
        setLoading(false);
      }
    };

    fetchNews();
  }, [marketName]);

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  if (loading) {
    return (
      <div className="mt-6 rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-50">
          <Newspaper className="h-4 w-4" />
          Related News
        </h3>
        <div className="grid gap-3 sm:grid-cols-2">
          {[...Array(4)].map((_, i) => (
            <div
              key={i}
              className="animate-pulse rounded-lg border border-zinc-800 bg-zinc-900/60 p-3"
            >
              <div className="mb-2 h-24 rounded bg-zinc-800" />
              <div className="mb-2 h-4 rounded bg-zinc-800" />
              <div className="h-3 w-2/3 rounded bg-zinc-800" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mt-6 rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-50">
          <Newspaper className="h-4 w-4" />
          Related News
        </h3>
        <p className="text-xs text-zinc-500">Unable to load news: {error}</p>
      </div>
    );
  }

  if (articles.length === 0) {
    return (
      <div className="mt-6 rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-50">
          <Newspaper className="h-4 w-4" />
          Related News
        </h3>
        <p className="text-xs text-zinc-500">No related news articles found.</p>
      </div>
    );
  }

  return (
    <div className="mt-6 rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-50">
        <Newspaper className="h-4 w-4" />
        Related News
      </h3>
      <div className="grid gap-3 sm:grid-cols-2">
        {articles.map((article, index) => (
          <a
            key={index}
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="group flex flex-col overflow-hidden rounded-lg border border-zinc-800 bg-zinc-900/60 transition hover:border-zinc-700 hover:bg-zinc-900"
          >
            {/* Thumbnail */}
            {article.urlToImage && (
              <div className="relative h-28 w-full overflow-hidden bg-zinc-800">
                <img
                  src={article.urlToImage}
                  alt={article.title}
                  className="h-full w-full object-cover transition group-hover:scale-105"
                  onError={(e) => {
                    // Hide broken images
                    (e.target as HTMLImageElement).style.display = "none";
                  }}
                />
              </div>
            )}

            {/* Content */}
            <div className="flex flex-1 flex-col p-3">
              <h4 className="mb-1 line-clamp-2 text-xs font-medium text-zinc-100 group-hover:text-white">
                {article.title}
              </h4>
              {article.description && (
                <p className="mb-2 line-clamp-2 text-[11px] text-zinc-400">
                  {article.description}
                </p>
              )}
              <div className="mt-auto flex items-center justify-between">
                <span className="text-[10px] text-zinc-500">
                  {article.source.name} · {formatDate(article.publishedAt)}
                </span>
                <ExternalLink className="h-3 w-3 text-zinc-500 transition group-hover:text-zinc-300" />
              </div>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
