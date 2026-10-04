import {expect,test} from "@playwright/test";

test("renders password recovery, reset, and verification entry points",async({page})=>{
  await page.goto("/forgot-password");
  await expect(page.getByRole("heading",{name:"Forgot password?"})).toBeVisible();
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByRole("button",{name:"Send reset link"})).toBeDisabled();

  await page.goto("/reset-password");
  await expect(page.getByRole("heading",{name:"Reset password"})).toBeVisible();
  await expect(page.getByLabel("Reset token")).toBeVisible();
  await expect(page.getByRole("button",{name:"Reset password"})).toBeDisabled();

  await page.goto("/verify-email");
  await expect(page.getByRole("heading",{name:"Verify email"})).toBeVisible();
  await expect(page.getByLabel("Verification token")).toBeVisible();
  await expect(page.getByRole("button",{name:"Verify email"})).toBeDisabled();
  await expect(page.getByLabel("Email for resend")).toBeVisible();
});
