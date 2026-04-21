#!/usr/bin/env node
import { readFile, writeFile, mkdir, access } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

const args = parseArgs(process.argv.slice(2));

if (args.help || (!args.url && !args.file && !args.stdin)) {
  printHelp();
  process.exit(args.help ? 0 : 1);
}

const url = args.url ?? args.positionals[0];
if (!url) {
  console.error('Missing source URL. Pass --url <url> or provide it as the first positional argument.');
  process.exit(1);
}

const html = await loadHtml(args);
const fixturesDir = path.resolve('test/fixtures');
await mkdir(fixturesDir, { recursive: true });

const fixtureName = sanitizeFixtureName(args.fixtureName ?? inferFixtureName(url));
const fixturePath = path.join(fixturesDir, `${fixtureName}.html`);

if (!args.force) {
  try {
    await access(fixturePath);
    console.error(`Fixture already exists: ${fixturePath}. Use --force to overwrite.`);
    process.exit(1);
  } catch {
    // does not exist
  }
}

await writeFile(fixturePath, html, 'utf-8');

console.log(`Saved fixture: ${fixturePath}`);
console.log('');
console.log('Suggested test stub:');
console.log('');
console.log(JSON.stringify({
  name: `${fixtureName} fixture`,
  file: `${fixtureName}.html`,
  url,
  expected: {
    parser: inferParser(url),
    title: 'TODO',
    price: 0,
    bedrooms: 0,
    bathrooms: 0,
    location: 'TODO',
    features: [],
    source: 'site_specific',
  },
}, null, 2));

function parseArgs(argv) {
  const out = { positionals: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--help' || arg === '-h') out.help = true;
    else if (arg === '--stdin') out.stdin = true;
    else if (arg === '--force') out.force = true;
    else if (arg === '--url') out.url = argv[++i];
    else if (arg === '--file') out.file = argv[++i];
    else if (arg === '--fixture-name' || arg === '--name') out.fixtureName = argv[++i];
    else out.positionals.push(arg);
  }
  return out;
}

async function loadHtml(args) {
  if (args.stdin) return readStdin();
  if (args.file) return readFile(path.resolve(args.file), 'utf-8');
  const response = await fetch(args.url ?? args.positionals[0], {
    headers: {
      'user-agent': 'Mozilla/5.0 (compatible; house-hunt-browser-extension-fixture-capture/0.1)',
      'accept-language': 'en-GB,en;q=0.9',
    },
  });
  if (!response.ok) {
    throw new Error(`Fetch failed: HTTP ${response.status}`);
  }
  return response.text();
}

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString('utf-8');
}

function inferFixtureName(url) {
  try {
    const u = new URL(url);
    const host = u.hostname.replace(/^www\./, '').replace(/\./g, '_');
    const tail = u.pathname.split('/').filter(Boolean).slice(-2).join('_') || 'listing';
    return `${host}_${tail}`;
  } catch {
    return 'fixture_listing';
  }
}

function sanitizeFixtureName(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'fixture_listing';
}

function inferParser(url) {
  try {
    const host = new URL(url).hostname.replace(/^www\./, '');
    if (host.endsWith('rightmove.co.uk')) return 'rightmove';
    if (host.endsWith('zoopla.co.uk')) return 'zoopla';
    if (host.endsWith('onthemarket.com')) return 'onthemarket';
  } catch {
    // ignore
  }
  return 'generic';
}

function printHelp() {
  console.log(`capture-fixture [url]\n\nOptions:\n  --url <url>            Source listing URL\n  --file <path>          Read HTML from a local file instead of fetching\n  --stdin                Read HTML from stdin\n  --fixture-name <name>  Override output filename (without .html)\n  --force                Overwrite existing fixture\n  -h, --help             Show this help\n\nExamples:\n  node scripts/capture-fixture.mjs https://www.rightmove.co.uk/properties/123\n  node scripts/capture-fixture.mjs --file page.html --url https://www.zoopla.co.uk/for-sale/details/42/\n  cat rendered.html | node scripts/capture-fixture.mjs --stdin --url https://www.onthemarket.com/details/7/\n`);
}
