import type { NextConfig } from "next";
import { config } from "dotenv";
import { resolve } from "path";

// Load env from root .env file
config({ path: resolve(__dirname, "../.env") });

const nextConfig: NextConfig = {
  env: {
    // Map to NEXT_PUBLIC_ for browser access (using anon key, not secret)
    NEXT_PUBLIC_SUPABASE_URL: process.env.SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.SUPABASE_ANON_KEY,
  },
};

export default nextConfig;
