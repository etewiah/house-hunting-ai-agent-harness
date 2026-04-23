#!/usr/bin/env node

/**
 * CLI wrapper around enrichListingsWithCommute and inferCommuteDestinationFromBrief
 * from commute-core.mjs.
 *
 * Usage:
 *   echo '[{...listing...}]' | node commute-cli.mjs --brief "3-bed near London" --mode transit
 *   echo '[{...listing...}]' | node commute-cli.mjs --destination "London" --mode transit
 *
 * Returns JSON array to stdout:
 *   [{...enriched listing...}, ...]
 */

import { stdin } from 'process';
import { enrichListingsWithCommute, inferCommuteDestinationFromBrief } from '../commute-core.mjs';

async function main() {
  const args = process.argv.slice(2);
  let brief = null;
  let destination = null;
  let mode = 'transit';

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--brief') {
      brief = args[++i];
    } else if (args[i] === '--destination') {
      destination = args[++i];
    } else if (args[i] === '--mode') {
      mode = args[++i];
    }
  }

  // Read listings from stdin
  let listings;
  try {
    const chunks = [];
    for await (const chunk of stdin) {
      chunks.push(chunk);
    }
    const input = Buffer.concat(chunks).toString('utf-8');
    listings = JSON.parse(input);
    if (!Array.isArray(listings)) {
      throw new Error('Input must be a JSON array of listings');
    }
  } catch (error) {
    console.error(`Error reading listings: ${error.message}`);
    process.exit(1);
  }

  // Infer destination from brief if not provided
  if (!destination && brief) {
    destination = inferCommuteDestinationFromBrief(brief);
  }

  // Enrich with commute
  try {
    const enriched = enrichListingsWithCommute(listings, destination, mode);
    console.log(JSON.stringify(enriched, null, 2));
  } catch (error) {
    console.error(`Error enriching commute: ${error.message}`);
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(`Fatal error: ${error.message}`);
  process.exit(1);
});
