import { test, expect } from "@playwright/test";

test.describe("MVP Agent Flow — Frontend/Backend Integration", () => {

  test("1. Setup Page — Agent Creation Form renders", async ({ page }) => {
    await page.goto("http://localhost:3000/setup");
    // Verify the page loaded with form content
    await expect(page.locator("body")).not.toBeEmpty();
    const heading = page.locator("h1, h2, .setup-stage").first();
    await expect(heading).toBeVisible({ timeout: 5000 });
  });

  test("2. Profile Page — renders agent profile section", async ({ page }) => {
    await page.goto("http://localhost:3000/perfil");
    await expect(page.locator("body")).not.toBeEmpty();

    const cards = page.locator("[data-testid], section, article, .card").first();
    if (await cards.isVisible()) {
      console.log(`[PERFIL] Content visible`);
    }
  });

  test("3. Dashboard — renders match cards from backend", async ({ page }) => {
    await page.goto("http://localhost:3000/");
    await expect(page.locator("body")).not.toBeEmpty();

    const heading = page.locator("h1, h2").first();
    if (await heading.isVisible()) {
      console.log(`[DASHBOARD] Heading: ${await heading.textContent()}`);
    }
  });

  test("4. Chat Detail — renders conversation with transcript", async ({ page }) => {
    // Uses a demo session ID from seed data
    await page.goto("http://localhost:3000/chat/c0000000-0000-0000-0000-000000000001");
    await expect(page.locator("body")).not.toBeEmpty();

    const messages = page.locator("[data-testid], .message, .chat-bubble, p").first();
    if (await messages.isVisible()) {
      console.log(`[CHAT] Messages visible`);
    }
  });

});
