#!/usr/bin/env node

/**
 * CLI wrapper around extractListingFromHtml from extractor-core.mjs.
 *
 * Usage:
 *   echo '<html>...</html>' | node extract-cli.mjs --url https://example.com/listing
 *   node extract-cli.mjs --url https://example.com/listing --file page.html
 *
 * Returns JSON to stdout:
 *   {
 *     "schemaVersion": "1.0",
 *     "listing": {...},
 *     "diagnostics": {...}
 *   }
 */

import { readFileSync, readSync } from 'fs';
import { stdin } from 'process';
import { extractListingFromHtml } from '../extractor-core.mjs';

async function main() {
  const args = process.argv.slice(2);
  let url = null;
  let filePath = null;
  let commuteMinutes = null;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--url') {
      url = args[++i];
    } else if (args[i] === '--file') {
      filePath = args[++i];
    } else if (args[i] === '--commute-minutes') {
      commuteMinutes = parseInt(args[++i], 10);
      if (isNaN(commuteMinutes)) commuteMinutes = null;
    }
  }

  if (!url) {
    console.error('Error: --url is required');
    process.exit(1);
  }

  let html;
  try {
    if (filePath) {
      html = readFileSync(filePath, 'utf-8');
    } else {
      // Read from stdin
      const chunks = [];
      for await (const chunk of stdin) {
        chunks.push(chunk);
      }
      html = Buffer.concat(chunks).toString('utf-8');
    }
  } catch (error) {
    console.error(`Error reading HTML: ${error.message}`);
    process.exit(1);
  }

  try {
    const result = extractListingFromHtml(url, html, commuteMinutes);
    const response = {
      schemaVersion: '1.0',
      ...result,
    };
    console.log(JSON.stringify(response, null, 2));
  } catch (error) {
    console.error(`Error extracting listing: ${error.message}`);
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(`Fatal error: ${error.message}`);
  process.exit(1);
});
