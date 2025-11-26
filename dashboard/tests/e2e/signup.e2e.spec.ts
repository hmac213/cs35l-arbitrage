import { test, expect } from "@playwright/test";

test.describe("Signup page", () => {
  test("shows signup form and validates mismatched passwords", async ({ page }) => {
    await page.goto("http://localhost:3000/signup");

    // Assertions for visibility
    await expect(
      page.getByRole("heading", { name: /sign up for arbitrage/i }),
    ).toBeVisible();
    await expect(page.getByLabel(/full name/i)).toBeVisible();
    await expect(page.getByLabel(/email address/i)).toBeVisible();
    await expect(page.getByLabel(/^password$/i)).toBeVisible();
    await expect(page.getByLabel(/confirm password/i)).toBeVisible();

    // Fill out the form with mismatched passwords
    await page.getByLabel(/full name/i).fill("Test User");
    await page.getByLabel(/email address/i).fill("test@example.com");
    await page.getByLabel(/^password$/i).fill("password123");
    await page.getByLabel(/confirm password/i).fill("different-password");

    await page.getByRole("button", { name: /create account/i }).click();

    // Assertion for text content (client-side validation message)
    await expect(page.getByText(/passwords do not match/i)).toBeVisible();
  });
});


