import { test, expect } from "@playwright/test";

test.describe("Protected dashboard route", () => {
  test("unauthenticated user is redirected to login from /dashboard", async ({
    page,
  }) => {
    await page.goto("http://localhost:3000/dashboard");

    // User should be kicked back to the login page
    await expect(page).toHaveURL("http://localhost:3000/");

    // Assertions for login page content
    await expect(
      page.getByRole("heading", { name: /sign in to arbitrage/i }),
    ).toBeVisible();
    await expect(page.getByLabel(/email address/i)).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
  });
});

