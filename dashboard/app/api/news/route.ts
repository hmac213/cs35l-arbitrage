import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const NEWS_API_KEY = process.env.NEWS_API_KEY;

export async function GET(request: Request): Promise<NextResponse> {
  try {
    const { searchParams } = new URL(request.url);
    const query = searchParams.get("q");

    if (!query) {
      return NextResponse.json(
        { error: "Missing search query" },
        { status: 400 }
      );
    }

    if (!NEWS_API_KEY) {
      return NextResponse.json(
        { error: "News API key not configured" },
        { status: 500 }
      );
    }

    const response = await fetch(
      `https://newsapi.org/v2/everything?q=${encodeURIComponent(query)}&sortBy=publishedAt&pageSize=6&language=en`,
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
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error fetching news:", error);
    return NextResponse.json(
      { error: "Failed to fetch news" },
      { status: 500 }
    );
  }
}
