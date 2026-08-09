import { test, expect } from "@playwright/test";

const viewports = [
  { name: "Desktop", width: 1440, height: 900 },
  { name: "Mobile", width: 375, height: 667 },
];

for (const vp of viewports) {
  test.describe(`Responsive - ${vp.name}`, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } });

    test("Setup page renders without overflow", async ({ page }) => {
      await page.goto("http://localhost:3000/setup");
      await expect(page.locator("body")).toBeVisible();
      await page.screenshot({ path: `../logs/screenshots/setup_${vp.name}.png` });
    });

    test("Bandeja page renders without overflow", async ({ page }) => {
      await page.goto("http://localhost:3000/bandeja");
      await expect(page.locator("body")).toBeVisible();
      await page.screenshot({ path: `../logs/screenshots/bandeja_${vp.name}.png` });
    });
  });
}
