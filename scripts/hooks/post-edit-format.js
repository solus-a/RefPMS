#!/usr/bin/env node
/**
 * PostToolUse Hook: Auto-format Python files after edits (RefPMS adapted)
 *
 * Runs after Edit tool use. If the edited file is a .py file,
 * uses `ruff format` or `black` to keep code consistent.
 */

const { execFileSync } = require('child_process');
const path = require('path');

const MAX_STDIN = 1024 * 1024; // 1MB limit

function run(rawInput) {
  try {
    const input = JSON.parse(rawInput);
    const filePath = input.tool_input?.file_path;

    if (filePath && /\.py$/.test(filePath)) {
      try {
        const resolvedFilePath = path.resolve(filePath);
        // Try ruff format first, then black
        try {
          execFileSync('ruff', ['format', resolvedFilePath], { stdio: 'ignore', timeout: 5000 });
        } catch {
          try {
            execFileSync('black', [resolvedFilePath], { stdio: 'ignore', timeout: 5000 });
          } catch {
            // No formatter found or failed — non-blocking
          }
        }
      } catch {
        // Non-blocking
      }
    }
  } catch {
    // Invalid input
  }

  return rawInput;
}

if (require.main === module) {
  let data = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', chunk => {
    if (data.length < MAX_STDIN) {
      data += chunk.substring(0, MAX_STDIN - data.length);
    }
  });
  process.stdin.on('end', () => {
    data = run(data);
    process.stdout.write(data);
    process.exit(0);
  });
}

module.exports = { run };
