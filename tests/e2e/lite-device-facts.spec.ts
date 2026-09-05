import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { installScenario, openTab, waitForLiteScreenToSettle, watchApiFailures } from './lite-test-helpers';

async function openDeviceDetails(page, name = 'Pocket Lab Lite Server') {
  await openTab(page, 'Devices', 'devices');
  await waitForLiteScreenToSettle(page, 'devices');
  const card = page.locator('.lite-device-card').filter({ hasText: name }).first();
  await expect(card).toBeVisible();
  await card.getByRole('button', { name: /Details|Review health/i }).click();
  const details = page.getByRole('region', { name: new RegExp(`${name}.*details`, 'i') });
  await expect(details).toBeVisible();
  return details;
}

async function setTheme(page, theme: 'daylight' | 'dark') {
  await page.addInitScript((value) => {
    document.documentElement.classList.toggle('theme-pocket-lite-dark', value === 'dark');
    document.documentElement.classList.toggle('theme-pocket-lite-daylight', value !== 'dark');
  }, theme);
}

async function blockingAxeViolations(page) {
  const result = await new AxeBuilder({ page }).include('[data-lite-screen-id="devices"]').analyze();
  return result.violations.filter((item) => ['serious', 'critical'].includes(item.impact || ''));
}

test('Home and Devices project the same canonical resource facts', async ({ page }) => {
  const failures = watchApiFailures(page);
  await installScenario(page, 'devices-resource-complete');
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');
  const home = page.locator('[data-lite-screen-id="home"]');
  await expect(home).toContainText('2.0 GiB free / 4.0 GiB');
  await expect(home).toContainText('CPU 12%');
  await expect(home).toContainText('125.0 GiB free / 250.0 GiB');
  const details = await openDeviceDetails(page);
  await expect(details).toContainText('2048 MB free / 4096 MB');
  await expect(details).toContainText('12%');
  await expect(details).toContainText('42 °C');
  expect(failures).toEqual([]);
});

for (const [scenario, expected] of [
  ['devices-resource-partial', 'Unsupported'], ['devices-resource-stale', 'Stale'],
  ['devices-resource-unsupported', 'Unsupported'], ['devices-resource-permission-denied', 'Permission denied'],
  ['devices-resource-missing', 'Not reported'],
] as const) {
  test(`resource evidence preserves ${scenario.replace('devices-resource-', '')} semantics`, async ({ page }) => {
    await installScenario(page, scenario); await page.goto('/?screen=devices');
    await expect(await openDeviceDetails(page)).toContainText(expected);
  });
}

for (const [scenario, expected] of [
  ['devices-capability-verified', 'Verified'], ['devices-capability-pending', 'Verification pending'],
  ['devices-capability-stale', 'Stale'], ['devices-capability-unsupported', 'Unsupported'],
  ['devices-capability-blocked', 'Blocked'], ['devices-capability-not-applicable', 'Not applicable'],
  ['devices-capability-missing', 'Not advertised'], ['devices-capability-unknown', 'Future Accelerator'],
] as const) {
  test(`capability lifecycle preserves ${scenario.replace('devices-capability-', '')} evidence`, async ({ page }) => {
    await installScenario(page, scenario); await page.goto('/?screen=devices');
    const details = await openDeviceDetails(page);
    await expect(details.getByRole('region', { name: 'Device capabilities' })).toContainText(expected);
  });
}

test('mixed capability evidence is data-driven rather than capability-id-specific UI', async ({ page }) => {
  await installScenario(page, 'devices-capability-mixed'); await page.goto('/?screen=devices');
  const region = (await openDeviceDetails(page)).getByRole('region', { name: 'Device capabilities' });
  for (const value of ['Verified','Verification pending','Unsupported','Future Accelerator']) await expect(region).toContainText(value);
});

for (const [scenario, expected] of [
  ['devices-services-mixed', '3 reported'], ['devices-services-stale', 'Last reported Online'],
  ['devices-services-unknown', 'Future Sidecar'], ['devices-services-disappeared', 'Not reported'],
] as const) {
  test(`runtime service list handles ${scenario.replace('devices-services-', '')}`, async ({ page }) => {
    await installScenario(page, scenario); await page.goto('/?screen=devices');
    const region = (await openDeviceDetails(page)).getByRole('region', { name: 'Runtime services' });
    await expect(region).toContainText(expected);
    await expect(region).not.toContainText(/token|password|nats:\/\/|\/data\/data\/|\/home\//i);
  });
}

for (const [scenario, expected] of [
  ['devices-software-current', 'Current'], ['devices-software-outdated', 'Update available'],
  ['devices-software-incompatible', 'Incompatible'], ['devices-software-stale', 'Stale'],
] as const) {
  test(`software posture renders ${scenario.replace('devices-software-', '')}`, async ({ page }) => {
    await installScenario(page, scenario); await page.goto('/?screen=devices');
    await expect((await openDeviceDetails(page)).locator('[data-device-fact-software]')).toContainText(expected);
  });
}

test('secondary device uses its own facts and offline saved facts stay visibly stale', async ({ page }) => {
  await installScenario(page, 'devices-secondary-offline-saved'); await page.goto('/?screen=devices');
  const details = await openDeviceDetails(page, 'Test-Phone-4');
  await expect(details).toContainText('Stale');
  await expect(details.getByRole('region', { name: 'Runtime services' })).toContainText('Not reported');
});

test('narrow mobile and long names do not overflow the Devices facts surface', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 }); await installScenario(page, 'devices-long-name');
  await page.goto('/?screen=devices'); await openDeviceDetails(page, 'Pocket Lab Edge Device With A Very Long Friendly Name For Layout Resilience Validation');
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
});

test('Device Facts support explicit daylight and dark themes', async ({ page }) => {
  await setTheme(page, 'daylight'); await installScenario(page, 'devices-resource-complete'); await page.goto('/?screen=devices');
  await expect(page.locator('html')).toHaveClass(/theme-pocket-lite-daylight/); await openDeviceDetails(page);
  await setTheme(page, 'dark'); await page.reload(); await expect(page.locator('html')).toHaveClass(/theme-pocket-lite-dark/); await openDeviceDetails(page);
});

test('mobile Device Details remains vertically scrollable with controls reachable', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 640 }); await installScenario(page, 'devices-resource-complete'); await page.goto('/?screen=devices');
  const details = await openDeviceDetails(page); await expect(details.getByRole('button', { name: 'Close device details' })).toBeVisible();
  expect(await details.evaluate((element) => element.scrollHeight >= element.clientHeight)).toBeTruthy();
  await details.evaluate((element) => element.scrollTo({ top: element.scrollHeight, behavior: 'instant' }));
  await expect(details.locator('details.lite-device-advanced-details summary')).toBeVisible();
});

test('Device Facts remain usable at 200 percent text', async ({ page }) => {
  await installScenario(page, 'devices-resource-complete'); await page.goto('/?screen=devices');
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; }); await openDeviceDetails(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
});

test('Device Facts preserve keyboard focus and progressive disclosure', async ({ page }) => {
  await installScenario(page, 'devices-resource-complete'); await page.goto('/?screen=devices');
  const disclosure = (await openDeviceDetails(page)).locator('details.lite-device-advanced-details');
  await disclosure.locator('summary').focus(); await expect(disclosure.locator('summary')).toBeFocused();
  await page.keyboard.press('Enter'); await expect(disclosure).toHaveAttribute('open', '');
});

test('Device Facts honor reduced motion and have no serious or critical Axe violations', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' }); await installScenario(page, 'devices-resource-complete'); await page.goto('/?screen=devices');
  const resource = (await openDeviceDetails(page)).locator('[data-device-fact-resource]').first();
  const reduced = await resource.evaluate((element) => { const style = getComputedStyle(element); return { animationDuration: style.animationDuration, transitionDuration: style.transitionDuration }; });
  expect(reduced.animationDuration).toBe('0s'); expect(reduced.transitionDuration).toBe('0s');
  expect(await blockingAxeViolations(page)).toEqual([]);
});
