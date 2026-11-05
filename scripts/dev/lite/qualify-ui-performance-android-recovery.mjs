import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const qualifier = fileURLToPath(new URL('./qualify-ui-performance-android-cdp.mjs', import.meta.url));
const child = spawn(process.execPath, [qualifier], {
  stdio: 'inherit',
  env: { ...process.env, LITE_ANDROID_QUALIFICATION_SCOPE: 'recovery' },
});

child.on('error', (error) => {
  console.error(`[ui-performance-android-recovery] ${error.message}`);
  process.exit(1);
});

child.on('exit', (code, signal) => {
  if (signal) {
    console.error(`[ui-performance-android-recovery] qualifier terminated by ${signal}`);
    process.exit(1);
  }
  process.exit(code ?? 1);
});
