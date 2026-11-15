// Render the HTML slides of "slides" clips to PNGs at the canvas picture size -> clips/<id>/step<N>.png.
//
//   node render_slides.mjs --project <dir> [--clip <id>] [--scale 1] [--wait-ms 400]
//
// A step opts in with "html": "slides/intro.html" (relative to the project) or "url": "http://...".
// Steps without either keep their "image" or reuse the previous slide (compose.py decides).
import { mkdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { chromium } from 'playwright';
import { loadVideoProject, parseArguments } from './video_project.mjs';

const DEFAULT_WAIT_MILLISECONDS = 400;

function slideAddress(project, step) {
  if (step.url) return step.url;
  if (step.html) return pathToFileURL(resolve(project.directory, step.html)).href;
  return null;
}

async function main() {
  const options = parseArguments(process.argv.slice(2));
  if (!options.project) throw new Error('usage: node render_slides.mjs --project <dir> [--clip <id>] [--scale 1] [--wait-ms 400]');
  const project = loadVideoProject(options.project);
  const scale = Number(options.scale ?? 1);
  const waitMilliseconds = Number(options['wait-ms'] ?? DEFAULT_WAIT_MILLISECONDS);
  const viewport = { width: Math.round(project.contentWidth / scale), height: Math.round(project.contentHeight / scale) };
  const slideClips = project.clips.filter((clip) => clip.kind === 'slides' && (!options.clip || clip.id === options.clip));

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport, deviceScaleFactor: scale });
  let renderedCount = 0;
  try {
    for (const clip of slideClips) {
      mkdirSync(project.clipDirectory(clip.id), { recursive: true });
      for (const [index, step] of clip.steps.entries()) {
        const address = slideAddress(project, step);
        if (!address) continue;
        await page.goto(address, { waitUntil: 'networkidle' });
        await page.waitForTimeout(waitMilliseconds);
        const outputPath = join(project.clipDirectory(clip.id), `step${index + 1}.png`);
        await page.screenshot({ path: outputPath });
        renderedCount += 1;
        console.log(`  ${clip.id}/step${index + 1} <- ${address}`);
      }
    }
  } finally {
    await browser.close();
  }
  console.log(`${renderedCount} slides rendered at ${project.contentWidth}x${project.contentHeight}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
