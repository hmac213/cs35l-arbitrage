import { NextResponse } from "next/server";
import { MarketPair } from "@/types/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function GET(): Promise<NextResponse<MarketPair[] | { error: string }>> {
  try {
    const response = await fetch(`${API_URL}/api/get_paired_markets`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
      // Revalidate every 30 seconds
      next: { revalidate: 30 },
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`Backend API error: ${response.status} - ${errorText}`);
      return NextResponse.json(
        { error: `Backend API error: ${response.status}` },
        { status: response.status }
      );
    }

    const data: MarketPair[] = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error fetching paired markets:", error);
    return NextResponse.json(
      { error: "Failed to fetch paired markets" },
      { status: 500 }
    );
  }
}

