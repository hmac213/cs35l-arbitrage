import { NextResponse } from "next/server";
import OpenAI from "openai";

export const dynamic = "force-dynamic";

const NEWS_API_KEY = process.env.NEWS_API_KEY;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const OPENAI_MODEL = process.env.OPENAI_MODEL || "gpt-5-nano";

const openai = new OpenAI({
  apiKey: OPENAI_API_KEY,
});

async function extractSearchTerms(marketName: string): Promise<string> {
  try {
    const response = await openai.chat.completions.create({
      model: OPENAI_MODEL,
      messages: [
        {
          role: "system",
          content: `You are a search query optimizer. Given a prediction market question, extract 2-4 key search terms that would find relevant news articles. Return ONLY the search terms separated by spaces, nothing else. Focus on the main subject/topic, key names, and important nouns. Remove filler words and question structure.`,
        },
        {
          role: "user",
          content: marketName,
        },
      ],
      max_tokens: 50,
      temperature: 0.3,
    });

    const searchTerms = response.choices[0]?.message?.content?.trim();
    return searchTerms || fallbackExtraction(marketName);
  } catch (error) {
    console.error("OpenAI extraction error:", error);
    return fallbackExtraction(marketName);
  }
}

// Fallback extraction if OpenAI fails
function fallbackExtraction(name: string): string {
  const stopWords = [
    "will", "be", "the", "a", "an", "in", "on", "at", "to", "for", "of", "by",
    "with", "from", "this", "that", "these", "those", "is", "are", "was", "were",
    "has", "have", "had", "do", "does", "did", "can", "could", "may", "might",
    "must", "shall", "should", "would", "yes", "no", "there", "their", "they",
    "and", "or", "but", "if", "then", "than", "so", "as", "it", "its",
    "hide", "new", "above", "below", "before", "after", "during", "end", "reach"
  ];

  let cleanedName = name.replace(/[?!.,;:'"$%()]/g, " ");

  stopWords.forEach((word) => {
    const regex = new RegExp(`\\b${word}\\b`, "gi");
    cleanedName = cleanedName.replace(regex, " ");
  });

  cleanedName = cleanedName.replace(/\s+/g, " ").trim();
  const words = cleanedName.split(" ").filter((word) => word.length >= 3);
  return words.slice(0, 3).join(" ");
}

export async function GET(request: Request): Promise<NextResponse> {
  try {
    const { searchParams } = new URL(request.url);
    const marketName = searchParams.get("market");

    if (!marketName) {
      return NextResponse.json(
        { error: "Missing market name" },
        { status: 400 }
      );
    }

    if (!NEWS_API_KEY) {
      return NextResponse.json(
        { error: "News API key not configured" },
        { status: 500 }
      );
    }

    // Extract search terms using OpenAI
    const searchQuery = await extractSearchTerms(marketName);
    console.log(`Market: "${marketName}" -> Search: "${searchQuery}"`);

    const response = await fetch(
      `https://newsapi.org/v2/everything?q=${encodeURIComponent(searchQuery)}&sortBy=publishedAt&pageSize=6&language=en`,
      {
        headers: {
          "X-Api-Key": NEWS_API_KEY,
        },
        cache: "no-store",
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`NewsAPI error: ${response.status} - ${errorText}`);
      return NextResponse.json(
        { error: `NewsAPI error: ${response.status}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    // Include the search query in response for debugging
    return NextResponse.json({ ...data, searchQuery });
  } catch (error) {
    console.error("Error fetching news:", error);
    return NextResponse.json(
      { error: "Failed to fetch news" },
      { status: 500 }
    );
  }
}
