// Web recording scenario for scripts/record/web.mjs — one block per narration line of the clip.
//   node <skill>/scripts/record/web.mjs --project videos/my-demo --clip 03 --scenario videos/my-demo/clip-scripts/clip03.mjs
const BASE_URL = process.env.DEMO_BASE_URL ?? 'http://localhost:3000';

export default async function scenario({ page, step, waitNarration, pause }) {
  // Off-camera set-up happens before step 1 (log in with env credentials, never literals).
  await page.goto(`${BASE_URL}/`);
  await page.waitForLoadState('networkidle');

  await step(1);
  await page.getByRole('link', { name: 'Pricing' }).click();
  await waitNarration();

  await step(2);
  await page.getByLabel('Email').fill('demo@example.com');
  await pause(0.5);
  await page.getByRole('button', { name: 'Subscribe' }).click();
  await waitNarration(1);
}
