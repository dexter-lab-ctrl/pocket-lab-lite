#!/usr/bin/env node
import { spawn } from 'node:child_process';

const ALLOWED_TOOLS = new Set([
  'browser_click',
  'browser_close',
  'browser_drag',
  'browser_fill_form',
  'browser_find',
  'browser_handle_dialog',
  'browser_hover',
  'browser_navigate',
  'browser_navigate_back',
  'browser_press_key',
  'browser_resize',
  'browser_select_option',
  'browser_snapshot',
  'browser_tabs',
  'browser_type',
  'browser_wait_for',
]);
const BLOCKED_TOOLS = new Set(['browser_run_code_unsafe']);

const [command, ...args] = process.argv.slice(2);
if (!command) {
  console.error('ERROR expected the official Playwright MCP command');
  process.exit(2);
}

const child = spawn(command, args, { stdio: ['pipe', 'pipe', 'inherit'] });

function write(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

function hasRequestId(message) {
  return Object.prototype.hasOwnProperty.call(message, 'id');
}

function reject(message, code, text) {
  if (!hasRequestId(message)) return;
  write({
    jsonrpc: '2.0',
    id: message.id,
    error: { code, message: text },
  });
}

function filterServerMessage(message) {
  if (message?.result?.tools && Array.isArray(message.result.tools)) {
    message.result.tools = message.result.tools.filter((tool) => ALLOWED_TOOLS.has(tool?.name));
  }
  return message;
}

function rejectClientToolCall(message) {
  if (message?.method !== 'tools/call') return false;
  const name = message.params?.name;
  if (typeof name !== 'string' || name.length === 0) {
    reject(message, -32602, 'Invalid tools/call request: params.name is required');
    return true;
  }
  if (ALLOWED_TOOLS.has(name) && !BLOCKED_TOOLS.has(name)) return false;
  reject(message, -32601, `Playwright MCP tool is not enabled: ${name}`);
  return true;
}

function relayLines(stream, transform, label) {
  let pending = '';

  function handle(line) {
    if (!line.trim()) return;
    try {
      transform(JSON.parse(line));
    } catch {
      process.stderr.write(`ERROR malformed JSON-RPC frame from ${label}\n`);
      child.kill();
      process.exitCode = 2;
    }
  }

  stream.setEncoding('utf8');
  stream.on('data', (chunk) => {
    pending += chunk;
    const lines = pending.split('\n');
    pending = lines.pop() ?? '';
    for (const line of lines) handle(line);
  });
  stream.on('end', () => handle(pending));
}

relayLines(process.stdin, (message) => {
  if (!rejectClientToolCall(message)) child.stdin.write(`${JSON.stringify(message)}\n`);
}, 'MCP client');
relayLines(child.stdout, (message) => write(filterServerMessage(message)), 'Playwright MCP');

child.on('exit', (code, signal) => {
  if (signal) process.exitCode = 2;
  else process.exitCode = code ?? 0;
});
child.on('error', (error) => {
  process.stderr.write(`ERROR could not start Playwright MCP: ${error.message}\n`);
  process.exitCode = 2;
});
