// Narration timing shared by the recorders (web.mjs, android.mjs): step(N) logs when narration line N starts,
// waitNarration() waits until that line has been spoken plus a settle time.
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { mediaDuration } from '../video_project.mjs';

const SETTLE_SECONDS = 0.6;
export const TAIL_SECONDS = 1.2;
const MILLISECONDS_PER_SECOND = 1000;

export function sleep(seconds) {
  return new Promise((resolveSleep) => setTimeout(resolveSleep, Math.max(0, seconds * MILLISECONDS_PER_SECOND)));
}

/**
 * @param {string} clipDirectory  folder holding step<N>.wav
 * @param {() => number} secondsNow  clock the step start times are logged in
 */
export function createNarrationTimer(clipDirectory, secondsNow) {
  const stepLog = [];
  let currentStep = { startedAt: 0, duration: 0 };

  const step = async (stepNumber) => {
    const duration = mediaDuration(join(clipDirectory, `step${stepNumber}.wav`));
    currentStep = { startedAt: secondsNow(), duration };
    stepLog.push({ stepNumber, startedAt: currentStep.startedAt });
  };
  const waitNarration = async (extraSeconds = 0) => {
    await sleep(currentStep.startedAt + currentStep.duration + SETTLE_SECONDS + extraSeconds - secondsNow());
  };
  const pause = (seconds) => sleep(seconds);

  return { step, waitNarration, pause, stepLog };
}

/** timeline.txt: "<step> <seconds from video start>" per line. Returns the written lines. */
export function writeTimeline(clipDirectory, entries) {
  const lines = entries.map(({ stepNumber, seconds }) => `${stepNumber} ${seconds.toFixed(3)}`);
  writeFileSync(join(clipDirectory, 'timeline.txt'), `${lines.join('\n')}\n`, 'utf8');
  return lines;
}
