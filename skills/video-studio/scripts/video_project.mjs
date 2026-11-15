// Node twin of video_project.py: loads video.json merged over scripts/defaults.json and the nearest
// .video-studio/defaults.json, so the Playwright scripts use the same canvas as compose.py.
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptsDirectory = dirname(fileURLToPath(import.meta.url));

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function deepMerge(base, override) {
  const merged = { ...base };
  for (const [key, value] of Object.entries(override)) {
    merged[key] = isPlainObject(value) && isPlainObject(merged[key]) ? deepMerge(merged[key], value) : value;
  }
  return merged;
}

function findWorkspaceDefaults(projectDirectory) {
  let directory = projectDirectory;
  while (true) {
    const candidate = join(directory, '.video-studio', 'defaults.json');
    if (existsSync(candidate)) return candidate;
    const parent = dirname(directory);
    if (parent === directory) return null;
    directory = parent;
  }
}

export function loadVideoProject(projectPath) {
  const directory = resolve(projectPath);
  const projectFile = join(directory, 'video.json');
  if (!existsSync(projectFile)) throw new Error(`missing ${projectFile}`);
  let settings = readJson(join(scriptsDirectory, 'defaults.json'));
  const workspaceDefaults = findWorkspaceDefaults(directory);
  if (workspaceDefaults) settings = deepMerge(settings, readJson(workspaceDefaults));
  settings = deepMerge(settings, readJson(projectFile));
  const usesSubtitleBand = settings.subtitles.mode === 'band';
  return {
    directory,
    settings,
    clips: settings.clips ?? [],
    clipDirectory: (clipId) => join(directory, 'clips', clipId),
    contentWidth: settings.canvas.width,
    contentHeight: usesSubtitleBand ? settings.canvas.height - settings.subtitles.bandHeight : settings.canvas.height,
  };
}

export function mediaDuration(path) {
  const output = execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path]);
  return Number.parseFloat(output.toString().trim());
}

export function parseArguments(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument.startsWith('--')) {
      const next = argv[index + 1];
      const hasValue = next !== undefined && !next.startsWith('--');
      options[argument.slice(2)] = hasValue ? next : true;
      if (hasValue) index += 1;
    }
  }
  return options;
}
