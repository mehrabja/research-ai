import{test,expect}from"@playwright/test";
test("login screen renders",async({page})=>{
  await page.goto("/login");
  await expect(page.getByRole("heading",{name:"Welcome back"})).toBeVisible();
  await expect(page.getByRole("button",{name:"Log in"})).toBeVisible();
});
