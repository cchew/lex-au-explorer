import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

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

test.describe("narrow screens", () => {
  test.use({ viewport: { width: 390, height: 800 } });

  test("TOC collapses into a Contents block above the Act text", async ({ page }) => {
    await page.goto("/reader/privacy-act-1988");
    const summary = page.getByText("Contents", { exact: true });
    const tocButton = page.getByRole("button", { name: "Dealing with credit information" });
    await expect(summary).toBeVisible();
    await expect(tocButton).toBeHidden();

    // Act text uses the full width, not an ~80px sliver beside a sidebar
    const pane = await page.locator(".content-pane").boundingBox();
    expect(pane?.width).toBeGreaterThan(300);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

    await summary.click();
    await expect(tocButton).toBeVisible();

    // picking an entry closes the block so the section is on screen
    await tocButton.click();
    await expect(tocButton).toBeHidden();
  });
});

test("desktop keeps the TOC open with no Contents toggle", async ({ page }) => {
  await page.goto("/reader/privacy-act-1988");
  await expect(page.getByText("Contents", { exact: true })).toBeHidden();
  await expect(page.getByRole("button", { name: "Dealing with credit information" })).toBeVisible();
});

test.describe("local terms", () => {
  const section = (page: import("@playwright/test").Page, heading: string) =>
    page.locator(".section-content").filter({ has: page.getByRole("heading", { name: heading }) });

  test("local definition popup shows pill, scope and the Act-wide line", async ({ page }) => {
    await page.goto("/reader/local-terms-act");
    const local = section(page, "Restricted disclosure").locator('span[data-term="disclose"][data-def-scope]');
    await expect(local.first()).toBeVisible();
    await local.first().hover();
    const tooltip = page.locator(".definition-tooltip");
    await expect(tooltip).toBeVisible({ timeout: 2000 });
    await expect(tooltip.locator(".definition-pill")).toHaveText("Local definition");
    await expect(tooltip).toContainText("This section only (s 27)");
    await expect(tooltip).toContainText("means to give access to protected information outside the agency");
    await expect(tooltip).toContainText("Differs from the Act-wide definition:");
    await expect(tooltip).toContainText("means to make known to any person");
    await expect(tooltip.locator(".definition-actwide-ref")).toHaveText("s 6");
  });

  test("same word outside the scope shows the Act-wide popup, no pill", async ({ page }) => {
    await page.goto("/reader/local-terms-act");
    const wide = section(page, "General use").locator('span[data-term="disclose"]');
    await expect(wide.first()).toBeVisible();
    await wide.first().hover();
    const tooltip = page.locator(".definition-tooltip");
    await expect(tooltip).toBeVisible({ timeout: 2000 });
    await expect(tooltip).toContainText("means to make known to any person");
    await expect(tooltip.locator(".definition-pill")).toHaveCount(0);
    await expect(tooltip).not.toContainText("This section only");
    await expect(tooltip).not.toContainText("Differs from the Act-wide definition");
  });

  test("local-only term shows pill and scope, and is not highlighted elsewhere", async ({ page }) => {
    await page.goto("/reader/local-terms-act");
    const inScope = section(page, "Inspections").locator('span[data-term="authorised officer"]');
    await expect(inScope.first()).toBeVisible();
    await inScope.first().hover();
    const tooltip = page.locator(".definition-tooltip");
    await expect(tooltip).toBeVisible({ timeout: 2000 });
    await expect(tooltip.locator(".definition-pill")).toHaveText("Local definition");
    await expect(tooltip).toContainText("This section only (s 41)");
    await expect(tooltip.locator(".definition-actwide")).toHaveCount(0);

    await expect(section(page, "General use")).toContainText("authorised officer");
    await expect(section(page, "General use").locator('[data-term="authorised officer"]')).toHaveCount(0);
  });

  test("Schedule-local term is highlighted after navigating to the Schedule", async ({ page }) => {
    await page.goto("/reader");
    await page.getByPlaceholder("Search legislation by title...").fill("Big Split");
    await page.getByTestId("search-option").filter({ hasText: "Big Split Act 2026" }).click();
    await expect(page.getByText("Part I content.")).toBeVisible();

    await page.getByRole("button", { name: "Schedule 1" }).first().click();
    const term = page.locator('.section-html span[data-term="sealed container"][data-def-scope]');
    await expect(term.first()).toBeVisible({ timeout: 3000 });
    await term.first().hover();
    const tooltip = page.locator(".definition-tooltip");
    await expect(tooltip).toBeVisible({ timeout: 2000 });
    await expect(tooltip.locator(".definition-pill")).toHaveText("Local definition");
    await expect(tooltip).toContainText("This Schedule only (Schedule 1)");

    // Back in Part I (its bundle also lists the term, scoped to the Schedule):
    // the word is present in the text but must not be highlighted.
    await page.mouse.move(0, 0);
    await page.getByRole("button", { name: "Section 1" }).first().click();
    const partText = page.locator(".section-html").filter({ hasText: "Part I content." });
    await expect(partText).toContainText("sealed container", { timeout: 3000 });
    await expect(partText.locator('[data-term="sealed container"]')).toHaveCount(0);
  });

  test("local popup has no axe violations", async ({ page }) => {
    await page.goto("/reader/local-terms-act");
    const local = section(page, "Restricted disclosure").locator('span[data-term="disclose"][data-def-scope]');
    await local.first().hover();
    await expect(page.locator(".definition-tooltip .definition-pill")).toBeVisible({ timeout: 2000 });
    const results = await new AxeBuilder({ page }).include(".definition-tooltip").analyze();
    expect(results.violations).toEqual([]);
  });

  // Pre-existing, not part of the local-terms feature: App.vue header/footer and
  // SourceTrustPanel use --color-ink-3 (#8b9095, 2.85-3.03:1) at 12-13px.
  // Excluded so this test gates only the feature's own markup; fix separately.
  test("whole reader page with local popup open has no axe violations (excl. pre-existing ink-3 text)", async ({ page }) => {
    await page.goto("/reader/local-terms-act");
    const local = section(page, "Restricted disclosure").locator('span[data-term="disclose"][data-def-scope]');
    await local.first().hover();
    await expect(page.locator(".definition-tooltip .definition-pill")).toBeVisible({ timeout: 2000 });
    const results = await new AxeBuilder({ page })
      .exclude(".subtitle")
      .exclude(".trust-meta")
      .exclude(".trust-verify")
      .exclude("footer")
      .analyze();
    expect(results.violations).toEqual([]);
  });
});
