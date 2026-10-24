import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

async function openDevices(page: Page, scenario = 'devices-online', appearance: 'dark' | 'light' | 'system' = 'dark') {
  await page.addInitScript(value => localStorage.setItem('pocketlab:appearance', value), appearance);
  await installScenario(page, scenario);
  await page.goto('/?screen=devices');
  await waitForLiteScreenToSettle(page, 'devices');
}
const states = [
  'devices-online','devices-offline','devices-repairing','devices-agent-stopped',
  'devices-remote-not-ready','devices-protected-host','devices-invite-ready',
  'devices-invite-mismatch','offline-saved'
];
for (const scenario of states) {
  test(`Devices preserves connection and recovery semantics: ${scenario}`, async ({page}) => {
    await openDevices(page, scenario);
    await expect(page.getByRole('heading',{name:'Devices',exact:true})).toBeVisible();
    await expect(page.getByRole('region',{name:'Pocket Lab device connections'}).or(page.getByRole('group',{name:'Pocket Lab device connections'})).first()).toBeVisible();
    await expect(page.getByRole('region',{name:'Workspace operational summary'}).or(page.locator('.lite-devices-horizon-summary'))).toBeVisible();
    await expect(page.locator('.lite-remote-access-panel')).toBeVisible();
  });
}
for (const appearance of ['dark','light'] as const) {
  for (const width of [320,360,375,390,430,768,1024,1440]) {
    test(`Devices ${appearance} responsive ${width}px and accessible connection states`, async ({page}) => {
      await page.setViewportSize({width,height:840});
      await page.emulateMedia({reducedMotion:'reduce'});
      await openDevices(page,'devices-online',appearance);
      await expect(page.locator('html')).toHaveAttribute('data-lite-theme',appearance);
      await expect(page.locator('.lite-device-relationship-node.is-server')).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2)).toBe(false);
      const accessibility = await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
      expect(accessibility.violations.filter(v=>['serious','critical'].includes(v.impact||''))).toEqual([]);
    });
  }
}
test('System appearance follows OS without changing Devices connection facts', async ({page}) => {
  await page.emulateMedia({colorScheme:'dark'});
  await openDevices(page,'devices-online','system');
  const previous = await page.locator('.lite-device-relationship-summary').innerText();
  await page.emulateMedia({colorScheme:'light'});
  await expect(page.locator('html')).toHaveAttribute('data-lite-theme','light');
  expect(await page.locator('.lite-device-relationship-summary').innerText()).toBe(previous);
});
test('desktop Devices Manage remains movable and keyboard-resizable',async({page})=>{
  await page.setViewportSize({width:1440,height:900});
  await openDevices(page);
  await page.getByRole('button',{name:/Manage /}).first().click();
  const panel=page.locator('[data-lite-details-panel-layout="desktop-movable"]');
  await expect(panel).toBeVisible();
  await panel.getByRole('button',{name:'Move device details panel'}).focus();
  await page.keyboard.press('ArrowLeft');
  await panel.getByRole('button',{name:'Resize device details panel'}).focus();
  await page.keyboard.press('Shift+ArrowDown');
  await panel.getByRole('button',{name:/Reset device details panel/}).click();
  const box=await panel.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(-2);
  expect(box!.x+box!.width).toBeLessThanOrEqual(1442);
});
test('mobile Devices Manage remains a sheet without desktop geometry controls',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await openDevices(page);
  await page.getByRole('button',{name:/Manage /}).first().click();
  await expect(page.locator('[data-lite-details-panel-layout="mobile-sheet"]')).toBeVisible();
  await expect(page.getByRole('button',{name:'Move device details panel'})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Resize device details panel'})).toHaveCount(0);
});
