import { test, expect } from "@playwright/test";

test("search -> select Act -> TOC navigate -> hover shows definition", async ({ page }) => {
  await page.goto("/reader");
  await page.getByPlaceholder("Search legislation by title...").fill("Privacy");
  await page.getByTestId("search-option").filter({ hasText: "Privacy Act 1988" }).click();
  await expect(page.getByRole("heading", { name: "Definitions" })).toBeVisible();

  const term = page.locator('[data-term="personal information"]');
  await term.hover();
  await expect(page.getByText("means information about an identified individual.")).toBeVisible({ timeout: 1000 });

  await expect(page.getByTestId("verification")).toContainText("current compilation on legislation.gov.au");
});

test("missing Act slug shows an inline error, not a crash", async ({ page }) => {
  await page.goto("/reader/does-not-exist");
  await expect(page.getByText(/HTTP 404/)).toBeVisible();
});

test("split-by-Part Act loads its first Part's sections", async ({ page }) => {
  await page.goto("/reader");
  await page.getByPlaceholder("Search legislation by title...").fill("Big Split");
  await page.getByTestId("search-option").filter({ hasText: "Big Split Act 2026" }).click();
  await expect(page.getByText("Part I content.")).toBeVisible();
});
