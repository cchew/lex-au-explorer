import { test, expect } from "@playwright/test";

test("search -> select Act -> TOC navigate -> hover shows definition", async ({ page }) => {
  await page.goto("/reader");
  await page.getByPlaceholder("Search legislation by title...").fill("Privacy");
  await page.getByTestId("search-option").filter({ hasText: "Privacy Act 1988" }).click();
  await expect(page.getByRole("heading", { name: "Definitions" })).toBeVisible();

  const term = page.locator('[data-term="personal information"]');
  await term.hover();
  await expect(page.getByText("means information about an identified individual.")).toBeVisible({ timeout: 2000 });

  await expect(page.getByTestId("verification")).toContainText("current compilation on legislation.gov.au");

  // Body-term highlighting: navigate to a non-definitions section and confirm
  // the runtime highlighter wrapped a defined term, then that hover AND
  // keyboard focus both surface the tooltip.
  await page.mouse.move(0, 0); // drop the previous hover so its tooltip dismisses
  await page.getByRole("button", { name: "Dealing with credit information" }).click();

  const bodyTerm = page.locator(
    '.section-html span[data-term="credit provider"][data-def-eid]',
  );
  await expect(bodyTerm.first()).toBeVisible({ timeout: 2000 });

  // hover -> tooltip
  await bodyTerm.first().hover();
  const tooltip = page.locator(".definition-tooltip");
  await expect(tooltip).toBeVisible({ timeout: 2000 });
  await expect(tooltip).toContainText("has the meaning given by section 6G");

  // move away -> tooltip dismissed
  await page.mouse.move(0, 0);
  await expect(tooltip).toBeHidden({ timeout: 2000 });

  // keyboard focus -> tooltip
  await bodyTerm.first().focus();
  await expect(tooltip).toBeVisible({ timeout: 2000 });
  await expect(tooltip).toContainText("has the meaning given by section 6G");

  // toggle off -> highlighter spans removed
  await page.getByLabel("Highlight defined terms").uncheck();
  await expect(
    page.locator('.section-html span[data-term="credit provider"][data-def-eid]'),
  ).toHaveCount(0);
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
