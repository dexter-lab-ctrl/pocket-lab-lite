import { defineConfig, devices } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { resolveLiteBrowser } from './scripts/dev/lite/resolve-browser.mjs';

const sni=readFileSync(join(homedir(),'.pocketlab-lite','qualification','caddy-sni'),'ascii').trim().toLowerCase();
if(!/^[a-z0-9](?:[a-z0-9.-]{0,252}[a-z0-9])?$/.test(sni)||!sni.includes('.')||sni.includes('..')) throw new Error('runtime TLS identity unavailable');
const browser=resolveLiteBrowser();
const launchOptions={...(browser.executable_path?{executablePath:browser.executable_path}:{}),args:[`--host-resolver-rules=MAP ${sni} 127.0.0.1`]};
const use={...devices['Desktop Chrome'],baseURL:`https://${sni}:18443`,launchOptions,ignoreHTTPSErrors:true,serviceWorkers:'allow' as const,trace:'off' as const,screenshot:'off' as const,video:'off' as const};
export default defineConfig({testDir:'./tests/e2e',testMatch:/lite-security-runtime\.spec\.ts/,timeout:30000,fullyParallel:false,workers:1,retries:0,reporter:[['json']],use,projects:[{name:'security-runtime',use}]});
