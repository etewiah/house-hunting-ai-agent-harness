#!/usr/bin/env node
import { readdir, access, readFile } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const testDir = path.resolve(__dirname, '../test');
const fixturesDir = path.join(testDir, 'fixtures');
const manifestPath = path.join(testDir, 'manifest.mjs');

const { fixtureManifest } = await import(pathToFileURL(manifestPath).href);
const fixtureFiles = (await readdir(fixturesDir)).filter((file) => file.endsWith('.html')).sort();
const manifestFiles = fixtureManifest.map((item) => item.file).sort();

const errors = [];
const warnings = [];

for (const item of fixtureManifest) {
  for (const field of ['name', 'variant', 'sourceType', 'notes', 'file', 'url', 'expected']) {
    if (!(field in item)) errors.push(`Missing field '${field}' in manifest entry for ${item.file ?? '<unknown file>'}`);
  }

  try {
    await access(path.join(fixturesDir, item.file));
  } catch {
    errors.push(`Manifest references missing fixture file: ${item.file}`);
  }

  if (!item.expected || typeof item.expected !== 'object') {
    errors.push(`Manifest entry ${item.file} is missing expected values.`);
    continue;
  }

  const expectationGroups = [
    ['parser', 'allowedParsers'],
    ['title', 'titleIncludes'],
    ['price', 'minPrice'],
    ['location', 'locationIncludes'],
    ['features', 'featuresAnyOf'],
  ];
  for (const [exactField, flexibleField] of expectationGroups) {
    if (!(exactField in item.expected) && !(flexibleField in item.expected)) {
      errors.push(`Manifest entry ${item.file} must provide expected.${exactField} or expected.${flexibleField}`);
    }
  }
  for (const field of ['bedrooms', 'bathrooms']) {
    if (!(field in item.expected)) {
      errors.push(`Manifest entry ${item.file} missing expected.${field}`);
    }
  }

  if ('features' in item.expected && !Array.isArray(item.expected.features)) {
    errors.push(`Manifest entry ${item.file} expected.features must be an array if present.`);
  }
  if ('featuresAnyOf' in item.expected && !Array.isArray(item.expected.featuresAnyOf)) {
    errors.push(`Manifest entry ${item.file} expected.featuresAnyOf must be an array if present.`);
  }

  if (item.expected.fieldSources && typeof item.expected.fieldSources !== 'object') {
    errors.push(`Manifest entry ${item.file} expected.fieldSources must be an object if present.`);
  }
}

for (const file of fixtureFiles) {
  if (!manifestFiles.includes(file)) {
    warnings.push(`Orphan fixture file not referenced by manifest: ${file}`);
  }
}

for (const file of manifestFiles) {
  if (!fixtureFiles.includes(file)) {
    errors.push(`Manifest references fixture file that does not exist on disk: ${file}`);
  }
}

const byParser = countBy(fixtureManifest, (item) => item.expected?.parser ?? 'unknown');
const byVariant = countBy(fixtureManifest, (item) => item.variant ?? 'unknown');

console.log('Fixture summary');
console.log('---------------');
console.log(`Manifest: ${manifestPath}`);
console.log(`Fixtures dir: ${fixturesDir}`);
console.log(`Entries: ${fixtureManifest.length}`);
console.log(`Parsers: ${formatCounts(byParser)}`);
console.log(`Variants: ${formatCounts(byVariant)}`);
console.log('');

if (warnings.length > 0) {
  console.log('Warnings');
  console.log('--------');
  for (const warning of warnings) console.log(`- ${warning}`);
  console.log('');
}

if (errors.length > 0) {
  console.error('Errors');
  console.error('------');
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}

console.log('Fixture validation passed.');

function countBy(items, getKey) {
  return items.reduce((acc, item) => {
    const key = getKey(item);
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});
}

function formatCounts(counts) {
  return Object.entries(counts).map(([key, value]) => `${key}=${value}`).join(', ');
}
