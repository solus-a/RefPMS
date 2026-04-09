#!/usr/bin/env node
/**
 * PostToolUse Hook: Run Python type-check or linting after edits (RefPMS adapted)
 *
 * Uses `ruff check` or `mypy` to verify Python code quality.
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
        // Try ruff check first (fast), then mypy
        try {
          execFileSync('ruff', ['check', '--fix', resolvedFilePath], { stdio: 'ignore', timeout: 5000 });
        } catch {
          try {
            execFileSync('mypy', [resolvedFilePath], { stdio: 'ignore', timeout: 10000 });
          } catch {
            // No linter found or failed — non-blocking
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
