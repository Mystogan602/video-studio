// Narration-driven recording of a web page with Playwright -> clips/<id>/raw.mp4 + timeline.txt.
//
//   node record/web.mjs --project <dir> --clip <id> --scenario <scenario.mjs> [--scale 1] [--headed]
//
// Scenario API: reference/adapters/footage.md; template: templates/web-scenario.example.mjs.
// The video is the picture area of the canvas (canvas width x height minus the subtitle band).
// --scale is the device scale factor: 1 = desktop layout, 3 = phone-like layout (CSS width = video width / 3).
import { execFileSync } from 'node:child_process';
import { mkdirSync, rmSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium } from 'playwright';
import { loadVideoProject, mediaDuration, parseArguments } from '../video_project.mjs';
import { TAIL_SECONDS, createNarrationTimer, sleep, writeTimeline } from './narration_timer.mjs';

const MILLISECONDS_PER_SECOND = 1000;

async function main() {
  const options = parseArguments(process.argv.slice(2));
  if (!options.project || !options.clip || !options.scenario) {
    throw new Error('usage: node record/web.mjs --project <dir> --clip <id> --scenario <scenario.mjs> [--scale 1] [--headed]');
  }
  const project = loadVideoProject(options.project);
  const clipDirectory = project.clipDirectory(options.clip);
  const videoDirectory = join(clipDirectory, 'web-video');
  rmSync(videoDirectory, { recursive: true, force: true });
  mkdirSync(videoDirectory, { recursive: true });
  const scale = Number(options.scale ?? 1);
  const videoSize = { width: project.contentWidth, height: project.contentHeight };
  const viewport = { width: Math.round(videoSize.width / scale), height: Math.round(videoSize.height / scale) };

  const { default: scenario } = await import(pathToFileURL(resolve(options.scenario)).href);
  const browser = await chromium.launch({ headless: !options.headed });
  const context = await browser.newContext({ viewport, deviceScaleFactor: scale, recordVideo: { dir: videoDirectory, size: videoSize } });
  const page = await context.newPage();
  const videoStartedAt = performance.now();
  const secondsSinceVideoStart = () => (performance.now() - videoStartedAt) / MILLISECONDS_PER_SECOND;
  const { step, waitNarration, pause, stepLog } = createNarrationTimer(clipDirectory, secondsSinceVideoStart);

  try {
    await scenario({ page, step, waitNarration, pause });
    await sleep(TAIL_SECONDS);
  } finally {
    await context.close();
    await browser.close();
  }
  const webmPath = await page.video().path();
  execFileSync('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', '-i', webmPath, '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', '30', join(clipDirectory, 'raw.mp4')]);
  rmSync(videoDirectory, { recursive: true, force: true });
  const timeline = writeTimeline(clipDirectory, stepLog.map(({ stepNumber, startedAt }) => ({ stepNumber, seconds: startedAt })));
  console.log(timeline.join('\n'));
  console.log(`raw duration: ${mediaDuration(join(clipDirectory, 'raw.mp4')).toFixed(1)}s`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
