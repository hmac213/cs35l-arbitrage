import { test, expect } from "@playwright/test";

// Use environment variables when provided; otherwise fall back to the
// shared test credentials you supplied.
const email =
  process.env.E2E_USER_EMAIL ?? "tester@gmail.com";
const password =
  process.env.E2E_USER_PASSWORD ?? "Tester1!";

test.describe("Auth → Dashboard end-to-end", () => {
  test("user can log in and see the dashboard", async ({ page }) => {

    await page.goto("http://localhost:3000/");

    // Fill and submit login form
    await page.getByLabel(/email address/i).fill(email);
    await page.getByLabel(/password/i).fill(password);

    // There are two "Continue" buttons (Google OAuth + form submit), so we
    // target the exact text to avoid Playwright strict mode violations.
    await page
      .getByRole("button", { name: "Continue", exact: true })
      .click();

    // Wait for redirect into dashboard
    await expect(page).toHaveURL(/\/dashboard$/);

    // Assert key dashboard UI elements
    await expect(
      page.getByRole("heading", { name: /arbitrage dashboard/i }),
    ).toBeVisible();

    // Budget input from the dashboard page
    await expect(page.getByLabel(/your budget/i)).toBeVisible();
  });
});

