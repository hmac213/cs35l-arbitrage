import { test, expect } from "@playwright/test";

test.describe("Login page", () => {
  test("shows login form and can navigate to signup", async ({ page }) => {
    await page.goto("http://localhost:3000/");

    // Assertions for visibility
    await expect(
      page.getByRole("heading", { name: /sign in to arbitrage/i }),
    ).toBeVisible();
    await expect(page.getByLabel(/email address/i)).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();

    // Click the "Sign up" link
    await page.getByRole("link", { name: /sign up/i }).click();

    // Assertions for navigation + content
    await expect(page).toHaveURL(/\/signup$/);
    await expect(
      page.getByRole("heading", { name: /sign up for arbitrage/i }),
    ).toBeVisible();
  });
});


