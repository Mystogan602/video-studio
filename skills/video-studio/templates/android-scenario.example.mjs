// Android recording scenario for scripts/record/android.mjs — one block per narration line of the clip.
//   node <skill>/scripts/record/android.mjs --project videos/my-demo --clip 01 --scenario videos/my-demo/clip-scripts/clip01.mjs
const APP_PACKAGE = 'com.example.app';

// Off camera: clean start on the screen the clip begins from.
export async function prepare({ device }) {
  await device.restartApp(APP_PACKAGE, 10);
}

export default async function scenario({ device, step, waitNarration }) {
  await step(1); // "Đầu tiên là phần tìm quán. …"
  await waitNarration();

  await step(2); // "Ở trang chủ, em bấm chip Phở, …"
  await device.tap(312, 640); // coordinates from the dry run
  await waitNarration(1);

  await step(3); // "Em kéo thanh bán kính …"
  await device.swipe(200, 1500, 820, 1500, 600);
  await waitNarration();
}
