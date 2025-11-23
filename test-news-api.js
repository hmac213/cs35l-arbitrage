// Test script for NewsAPI with sample market names
const NEWS_API_KEY = "d4d3f959e569458487574f844540960a";

// Sample market names (similar to what you'd see in prediction markets)
const sampleMarketNames = [
  "Will Bitcoin reach $100,000 by end of 2024?",
  "Will Donald Trump win the 2024 presidential election?",
  "Will the Fed cut interest rates in December 2024?",
  "Will Tesla stock close above $300 this month?",
  "Will there be a TikTok ban in the US?",
];

// Extract search terms - improved version with word boundaries
function extractSearchTerms(name) {
  // List of stop words to remove (using word boundaries)
  const stopWords = [
    "will", "be", "the", "a", "an", "in", "on", "at", "to", "for", "of", "by",
    "with", "from", "this", "that", "these", "those", "is", "are", "was", "were",
    "has", "have", "had", "do", "does", "did", "can", "could", "may", "might",
    "must", "shall", "should", "would", "yes", "no", "there", "their", "they",
    "and", "or", "but", "if", "then", "than", "so", "as", "it", "its",
    "hide", "new", "above", "below", "before", "after", "during", "end", "reach"
  ];

  // Remove punctuation and special characters first
  let cleanedName = name.replace(/[?!.,;:'"$%()]/g, " ");

  // Remove stop words using word boundaries
  stopWords.forEach((word) => {
    const regex = new RegExp(`\\b${word}\\b`, "gi");
    cleanedName = cleanedName.replace(regex, " ");
  });

  // Clean up whitespace
  cleanedName = cleanedName.replace(/\s+/g, " ").trim();

  // Get meaningful words (at least 3 chars)
  const words = cleanedName.split(" ").filter((word) => word.length >= 3);

  // Return up to 3 key terms for better search results
  return words.slice(0, 3).join(" ");
}

async function testNewsAPI(marketName) {
  const searchQuery = extractSearchTerms(marketName);
  console.log(`\n${"=".repeat(60)}`);
  console.log(`Market: "${marketName}"`);
  console.log(`Search Query: "${searchQuery}"`);
  console.log("=".repeat(60));

  if (!searchQuery) {
    console.log("❌ No search query extracted");
    return;
  }

  try {
    const url = `https://newsapi.org/v2/everything?q=${encodeURIComponent(searchQuery)}&sortBy=publishedAt&pageSize=4&language=en`;

    const response = await fetch(url, {
      headers: {
        "X-Api-Key": NEWS_API_KEY,
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.log(`❌ API Error: ${response.status} - ${errorText}`);
      return;
    }

    const data = await response.json();

    if (data.status === "ok") {
      console.log(`✅ Found ${data.totalResults} total results`);

      const articlesWithImages = data.articles.filter(
        (article) => article.urlToImage && article.title !== "[Removed]"
      );

      console.log(`📷 Articles with images: ${articlesWithImages.length}`);

      if (articlesWithImages.length > 0) {
        console.log("\nTop articles:");
        articlesWithImages.slice(0, 3).forEach((article, i) => {
          console.log(`\n  ${i + 1}. ${article.title}`);
          console.log(`     Source: ${article.source.name}`);
          console.log(`     Date: ${new Date(article.publishedAt).toLocaleDateString()}`);
          console.log(`     Image: ${article.urlToImage ? "✓" : "✗"}`);
        });
      } else {
        console.log("\n  No articles with images found");
        if (data.articles.length > 0) {
          console.log("\n  Articles without images:");
          data.articles.slice(0, 2).forEach((article, i) => {
            console.log(`    ${i + 1}. ${article.title}`);
          });
        }
      }
    } else {
      console.log(`❌ API returned error: ${data.message}`);
    }
  } catch (error) {
    console.log(`❌ Fetch error: ${error.message}`);
  }
}

async function main() {
  console.log("🧪 Testing NewsAPI with sample market names\n");

  for (const marketName of sampleMarketNames) {
    await testNewsAPI(marketName);
  }

  console.log("\n" + "=".repeat(60));
  console.log("Test complete!");
}

main();
