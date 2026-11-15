// Narration-driven screen recording of an Android device over adb -> clips/<id>/raw.mp4 + timeline.txt.
// Runs on Windows, macOS and Linux (Node >= 18 + adb; no npm packages needed).
//
//   node record/android.mjs --project <dir> --clip <id> --scenario <scenario.mjs> [--serial <device>]
//
// Scenario API: reference/adapters/footage.md; template: templates/android-scenario.example.mjs.
// A failed scenario (or Ctrl+C) stops screenrecord and deletes the take on the device.
import { spawn, spawnSync } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { loadVideoProject, mediaDuration, parseArguments } from '../video_project.mjs';
import { TAIL_SECONDS, createNarrationTimer, sleep, writeTimeline } from './narration_timer.mjs';

const LEAD_IN_SECONDS = 1.2;
const SCREEN_RECORD_BIT_RATE = 8_000_000;
const SCREEN_RECORD_LIMIT_SECONDS = 180;
const SCREEN_RECORD_LIMIT_WARNING_MARGIN_SECONDS = 10;
const SCREEN_RECORD_EXIT_TIMEOUT_MILLISECONDS = 15_000;
const AFTER_STOP_SECONDS = 1;
const DEFAULT_RESTART_WAIT_SECONDS = 8;
const DEFAULT_SWIPE_MILLISECONDS = 300;
const MILLISECONDS_PER_SECOND = 1000;
const REMOTE_START_TIME_PATH = '/sdcard/video-studio-t0';
const REMOTE_SCREEN_DUMP_PATH = '/sdcard/video-studio-ui.xml';
const CLIP_ID_PATTERN = /^[\w-]+$/;
const PRINTABLE_ASCII_PATTERN = /^[\x20-\x7E]*$/;

const hostSeconds = () => (performance.timeOrigin + performance.now()) / MILLISECONDS_PER_SECOND;

/** Single-quote a value for the device's /system/bin/sh. */
function quoteForDeviceShell(value) {
  return `'${String(value).replaceAll("'", `'\\''`)}'`;
}

function decodeXmlEntities(text) {
  return text
    .replace(/&#(\d+);/g, (_, code) => String.fromCodePoint(Number(code)))
    .replace(/&#x([0-9a-f]+);/gi, (_, code) => String.fromCodePoint(Number.parseInt(code, 16)))
    .replaceAll('&quot;', '"')
    .replaceAll('&apos;', "'")
    .replaceAll('&lt;', '<')
    .replaceAll('&gt;', '>')
    .replaceAll('&amp;', '&');
}

function readXmlAttribute(tag, name) {
  const match = tag.match(new RegExp(`\\s${name}="([^"]*)"`));
  return match ? decodeXmlEntities(match[1]) : '';
}

/** uiautomator dump -> [{ text, contentDescription, centerX, centerY }]. */
function parseScreenNodes(xml) {
  const nodes = [];
  for (const [tag] of xml.matchAll(/<node\b[^>]*>/g)) {
    const bounds = readXmlAttribute(tag, 'bounds').match(/\d+/g)?.map(Number);
    if (!bounds || bounds.length !== 4) continue;
    const [left, top, right, bottom] = bounds;
    nodes.push({
      text: readXmlAttribute(tag, 'text'),
      contentDescription: readXmlAttribute(tag, 'content-desc'),
      centerX: Math.round((left + right) / 2),
      centerY: Math.round((top + bottom) / 2),
    });
  }
  return nodes;
}

function createDevice(adbPath, serial) {
  const targetArguments = serial ? ['-s', serial] : [];

  /** Raw adb call; returns stdout. Throws with adb's stderr unless allowFailure. */
  const adb = (adbArguments, { allowFailure = false } = {}) => {
    const result = spawnSync(adbPath, [...targetArguments, ...adbArguments], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
    if (result.error) throw new Error(`cannot run ${adbPath} (${result.error.message}); install Android platform-tools or set ADB_PATH`);
    if (result.status !== 0 && !allowFailure) {
      throw new Error(`adb ${adbArguments.join(' ')} failed (${result.status}): ${result.stderr.trim()}`);
    }
    return result.stdout;
  };
  const shell = (command, options) => adb(['shell', command], options);

  const screenNodes = () => {
    // Some ROMs print a harmless stack trace during a dump; the file is still written.
    shell(`uiautomator dump ${REMOTE_SCREEN_DUMP_PATH}`, { allowFailure: true });
    return parseScreenNodes(adb(['exec-out', 'cat', REMOTE_SCREEN_DUMP_PATH]));
  };

  /** Centre of the first node whose text or content-desc is exactly label, or null. Costs 2-5 s. */
  const findText = (label) => {
    const node = screenNodes().find((candidate) => candidate.text === label || candidate.contentDescription === label);
    return node ? { x: node.centerX, y: node.centerY } : null;
  };

  const tap = async (x, y) => {
    shell(`input tap ${Math.round(x)} ${Math.round(y)}`);
  };

  return {
    adb,
    shell,
    tap,
    swipe: async (fromX, fromY, toX, toY, durationMilliseconds = DEFAULT_SWIPE_MILLISECONDS) => {
      shell(`input swipe ${[fromX, fromY, toX, toY, durationMilliseconds].map(Math.round).join(' ')}`);
    },
    key: async (keyCode) => {
      shell(`input keyevent ${quoteForDeviceShell(keyCode)}`);
    },
    /** ASCII only: `input text` cannot type accented characters. */
    typeText: async (text) => {
      if (!PRINTABLE_ASCII_PATTERN.test(text)) throw new Error(`typeText: ASCII only, got ${JSON.stringify(text)}`);
      shell(`input text ${quoteForDeviceShell(text.replaceAll(' ', '%s'))}`);
    },
    restartApp: async (packageName, waitSeconds = DEFAULT_RESTART_WAIT_SECONDS) => {
      shell(`am force-stop ${quoteForDeviceShell(packageName)}`);
      shell(`monkey -p ${quoteForDeviceShell(packageName)} -c android.intent.category.LAUNCHER 1`, { allowFailure: true });
      await sleep(waitSeconds);
    },
    openDeepLink: async (url, packageName = '') => {
      const target = packageName ? ` ${quoteForDeviceShell(packageName)}` : '';
      shell(`am start -W -a android.intent.action.VIEW -d ${quoteForDeviceShell(url)}${target}`);
    },
    screenNodes,
    findText,
    /** Tap the node whose text is exactly label; options.x keeps the row's vertical centre but taps at that x. */
    tapText: async (label, { x } = {}) => {
      const center = findText(label);
      if (!center) throw new Error(`tapText: '${label}' not found on screen`);
      await tap(x ?? center.x, center.y);
    },
    hasText: async (text) =>
      screenNodes().some((node) => node.text.includes(text) || node.contentDescription.includes(text)),
  };
}

class ScreenRecording {
  constructor(device, adbPath, serial, clipId) {
    this.device = device;
    this.adbPath = adbPath;
    this.serial = serial;
    this.remoteVideoPath = `/sdcard/video-studio-${clipId}.mp4`;
  }

  start() {
    // Host clock minus device clock, measured around one round trip.
    const before = hostSeconds();
    const deviceNow = Number.parseFloat(this.device.shell('date +%s.%N'));
    const after = hostSeconds();
    this.clockOffset = (before + after) / 2 - deviceNow;
    const remoteCommand =
      `rm -f ${this.remoteVideoPath}; date +%s.%N > ${REMOTE_START_TIME_PATH}; ` +
      `exec screenrecord --bit-rate ${SCREEN_RECORD_BIT_RATE} ${this.remoteVideoPath}`;
    const targetArguments = this.serial ? ['-s', this.serial] : [];
    this.process = spawn(this.adbPath, [...targetArguments, 'shell', remoteCommand], { stdio: 'ignore' });
    this.exited = new Promise((resolveExit) => this.process.once('exit', resolveExit));
    this.startedAt = hostSeconds();
  }

  async stopScreenRecord() {
    this.device.shell('pkill -INT screenrecord', { allowFailure: true });
    await Promise.race([this.exited, sleep(SCREEN_RECORD_EXIT_TIMEOUT_MILLISECONDS / MILLISECONDS_PER_SECOND)]);
    await sleep(AFTER_STOP_SECONDS);
  }

  removeRemoteFiles() {
    this.device.shell(`rm -f ${this.remoteVideoPath} ${REMOTE_START_TIME_PATH} ${REMOTE_SCREEN_DUMP_PATH}`, { allowFailure: true });
  }

  /** Pull the take to rawPath; returns the device time (seconds) when screenrecord started. */
  pull(rawPath) {
    const deviceStart = Number.parseFloat(this.device.shell(`cat ${REMOTE_START_TIME_PATH}`));
    this.device.adb(['pull', this.remoteVideoPath, rawPath]);
    this.removeRemoteFiles();
    return deviceStart;
  }
}

async function main() {
  const options = parseArguments(process.argv.slice(2));
  if (!options.project || !options.clip || !options.scenario) {
    throw new Error('usage: node record/android.mjs --project <dir> --clip <id> --scenario <scenario.mjs> [--serial <device>]');
  }
  if (!CLIP_ID_PATTERN.test(options.clip)) throw new Error(`clip id must be letters, digits, - or _ (got ${options.clip})`);
  const project = loadVideoProject(options.project);
  const clipDirectory = project.clipDirectory(options.clip);
  mkdirSync(clipDirectory, { recursive: true });
  const adbPath = process.env.ADB_PATH || 'adb';
  const serial = options.serial || process.env.ANDROID_SERIAL || '';
  const device = createDevice(adbPath, serial);
  const scenarioModule = await import(pathToFileURL(resolve(options.scenario)).href);

  if (scenarioModule.prepare) await scenarioModule.prepare({ device, pause: sleep });

  const recording = new ScreenRecording(device, adbPath, serial, options.clip);
  const timer = createNarrationTimer(clipDirectory, hostSeconds);
  const step = async (stepNumber) => {
    if (hostSeconds() - recording.startedAt > SCREEN_RECORD_LIMIT_SECONDS - SCREEN_RECORD_LIMIT_WARNING_MARGIN_SECONDS) {
      console.warn(`clip ${options.clip}: close to the ${SCREEN_RECORD_LIMIT_SECONDS}s screenrecord limit — split the clip`);
    }
    await timer.step(stepNumber);
  };
  const discardOnInterrupt = () => {
    device.shell('pkill -INT screenrecord', { allowFailure: true });
    recording.removeRemoteFiles();
    process.exit(130);
  };

  recording.start();
  process.once('SIGINT', discardOnInterrupt);
  try {
    await sleep(LEAD_IN_SECONDS);
    await scenarioModule.default({ device, step, waitNarration: timer.waitNarration, pause: timer.pause });
    await sleep(TAIL_SECONDS);
    await recording.stopScreenRecord();
  } catch (error) {
    await recording.stopScreenRecord();
    recording.removeRemoteFiles();
    throw error;
  } finally {
    process.removeListener('SIGINT', discardOnInterrupt);
  }

  const rawPath = join(clipDirectory, 'raw.mp4');
  const deviceStart = recording.pull(rawPath);
  const entries = timer.stepLog.map(({ stepNumber, startedAt }) => ({
    stepNumber,
    seconds: startedAt - recording.clockOffset - deviceStart,
  }));
  console.log(writeTimeline(clipDirectory, entries).join('\n'));
  console.log(`raw duration: ${mediaDuration(rawPath).toFixed(1)}s`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
