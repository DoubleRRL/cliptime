import { expect, test } from "@playwright/test";

test("local user can open the console and save preferences", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("link", { name: "Cliptime" })).toBeVisible();
  await expect(page.getByRole("button", { name: /new session/i })).toBeVisible();

  await page.goto("/settings");
  await page.getByRole("button", { name: /save preferences/i }).click();
  await expect(page.getByText(/preferences saved/i)).toBeVisible();
});

test("console header settings link navigates away from the app", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("link", { name: /settings/i }).click();
  await expect(page).toHaveURL(/\/settings$/);
  await expect(page.getByRole("button", { name: /save preferences/i })).toBeVisible();
});

test("local user can access the admin dashboard", async ({ page }) => {
  await page.goto("/admin");

  await expect(page.getByText(/admin dashboard/i)).toBeVisible();
  await expect(
    page.getByRole("heading", { name: /currently processing tasks/i }),
  ).toBeVisible();
});

test("sign-in redirects to home in local single-user mode", async ({ page }) => {
  await page.goto("/sign-in");
  await expect(page).toHaveURL("/");
});
