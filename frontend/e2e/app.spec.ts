import { expect, test } from "@playwright/test";

test("local user can open the console and save preferences", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("link", { name: "Cliptime" })).toBeVisible();
  await expect(page.getByRole("button", { name: /new session/i })).toBeVisible();

  await page.getByRole("button", { name: /settings/i }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: /save preferences/i }).click();
  await expect(page.getByText(/preferences saved/i)).toBeVisible();
  await expect(page).toHaveURL("/");
});

test("console header settings button opens modal without leaving home", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: /settings/i }).click();
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("button", { name: /save preferences/i })).toBeVisible();
});

test("local user can access the admin dashboard", async ({ page }) => {
  await page.goto("/admin");

  await expect(page.getByText(/admin dashboard/i)).toBeVisible();
  await expect(
    page.getByRole("heading", { name: /currently processing tasks/i }),
  ).toBeVisible();
});
