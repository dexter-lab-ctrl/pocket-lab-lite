import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// Authored mock-only qualification — NOT RUN in the implementation session.
async function home(page: Page, theme: 'light' | 'dark' = 'light', scenario = 'healthy') {
  await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), theme);
  await installScenario(page, scenario);
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');
}
const targets = [
  '.lite-home-refined .lite-page-header',
  '.lite-home-command-hero',
  '.lite-home-command-hero h2',
  '.lite-home-command-details',
  '.lite-home-overview-grid',
  '.lite-home-overview-grid > button:nth-child(1)',
  '.lite-home-overview-grid > button:nth-child(4)',
  '.lite-home-lower-grid',
];
async function geometry(page: Page, selectors: string[]) {
  return page.evaluate((items) => items.map((selector) => {
    const el = document.querySelector(selector);
    if (!el) throw new Error('Missing geometry target: ' + selector);
    const box = el.getBoundingClientRect();
    return { selector, x: box.x, y: box.y, width: box.width, height: box.height };
  }), selectors);
}
function sameGeometry(before: Awaited<ReturnType<typeof geometry>>, after: Awaited<ReturnType<typeof geometry>>) {
  expect(after.map((x) => x.selector)).toEqual(before.map((x) => x.selector));
  before.forEach((value, index) => {
    for (const key of ['x','y','width','height'] as const)
      expect(Math.abs(value[key] - after[index][key]), value.selector + '.' + key).toBeLessThanOrEqual(1.5);
  });
}

for (const width of [320,360,390,430,768,1280,1600]) {
  test('Command Home viewport ' + width + 'px stays within page boundaries', async ({page}) => {
    await page.setViewportSize({width,height:820});
    await page.emulateMedia({reducedMotion:'reduce'});
    await home(page);
    await expect(page.locator('[data-home-hero-state]')).toBeVisible();
    await expect(page.locator('.lite-home-overview-grid > button')).toHaveCount(4);
    for (const name of ['Apps','Devices','Safety','Backups'])
      await expect(page.getByRole('button',{name:'Open '+name})).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2)).toBe(false);
  });
}

test('Mobile grouped navigation supports nested sections, Back, Escape and focus restoration', async ({page}) => {
  await page.setViewportSize({width:390,height:800});
  await home(page,'dark');
  const opener = page.getByRole('button',{name:'Workspace details'});
  await opener.focus();
  await opener.click();
  const dialog = page.getByRole('dialog',{name:'Workspace details'});
  await expect(dialog.locator('[data-home-settings-view="index"]')).toBeVisible();
  await dialog.getByRole('button',{name:'Service health'}).click();
  await expect(dialog.locator('[data-home-settings-view="section"]')).toBeVisible();
  await expect(dialog.getByRole('heading',{name:'Service health'})).toBeVisible();
  await expect(dialog.locator('[data-home-workflow-state]')).toBeVisible();
  await dialog.getByRole('button',{name:/All workspace details sections/}).click();
  await expect(dialog.locator('[data-home-settings-view="index"]')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test('Recent activity provides grouped root, History and backend-owned review behavior', async ({page}) => {
  await page.setViewportSize({width:390,height:800});
  await home(page);
  await page.getByRole('button',{name:/View all activity/}).click();
  const dialog = page.getByRole('dialog',{name:'Recent activity'});
  await expect(dialog.locator('[data-home-settings-view="index"]')).toBeVisible();
  await dialog.getByRole('button',{name:'History'}).click();
  await expect(dialog.getByText(/Marking history reviewed changes only your private review position/)).toBeVisible();
  await dialog.getByRole('button',{name:/All activity sections/}).click();
  await expect(dialog.locator('[data-home-settings-view="index"]')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
});

test('Daylight and Dark use identical Home and panel geometry for the same data', async ({page}) => {
  await page.setViewportSize({width:1280,height:900});
  await home(page,'light');
  const daylight = await geometry(page,targets);
  await page.evaluate(() => { document.documentElement.dataset.liteTheme='dark'; });
  const dark = await geometry(page,targets);
  sameGeometry(daylight,dark);
  await page.getByRole('button',{name:'Workspace details'}).click();
  const panelTargets=['.lite-home-details-panel','.lite-home-settings-workspace',
    '.lite-home-settings-navigation','.lite-home-settings-row:first-of-type','.lite-home-settings-detail'];
  const darkPanel = await geometry(page,panelTargets);
  await page.evaluate(() => {document.documentElement.dataset.liteTheme='light';});
  const lightPanel = await geometry(page,panelTargets);
  sameGeometry(darkPanel,lightPanel);
});

test('Narrow resized desktop panel uses the actual container for settings navigation', async ({page}) => {
  await page.setViewportSize({width:1280,height:900});
  await home(page);
  await page.getByRole('button',{name:'Workspace details'}).click();
  const dialog = page.getByRole('dialog',{name:'Workspace details'});
  const resize = dialog.getByRole('button',{name:'Resize Workspace details panel'});
  await resize.focus();
  for (let i=0;i<6;i++) await page.keyboard.press('ArrowLeft');
  await expect(dialog.locator('.lite-home-settings-navigation')).toBeVisible();
  const overflow=await dialog.evaluate((node)=>node.scrollWidth>node.clientWidth+2);
  expect(overflow).toBe(false);
});

test('200% text, mobile scroll containment and reduced motion keep destination cards usable', async ({page}) => {
  await page.setViewportSize({width:320,height:740});
  await page.emulateMedia({reducedMotion:'reduce'});
  await home(page,'dark');
  await page.addStyleTag({content:'html { font-size: 200% !important; }'});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2)).toBe(false);
  await page.getByRole('button',{name:'Workspace details'}).click();
  const dialog=page.getByRole('dialog',{name:'Workspace details'});
  await expect(dialog.locator('.lite-home-settings-navigation')).toBeVisible();
  expect(await dialog.evaluate((node)=>node.scrollWidth>node.clientWidth+2)).toBe(false);
});

for (const theme of ['light','dark'] as const) {
  test('Command Home and grouped portal WCAG checks — '+theme,async ({page})=>{
    await home(page,theme);
    const axe=new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']);
    expect((await axe.analyze()).violations).toEqual([]);
    await page.getByRole('button',{name:'Workspace details'}).click();
    expect((await new AxeBuilder({page}).include('[role="dialog"]')
      .withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze()).violations).toEqual([]);
  });
}

for (const scenario of ['healthy','lifecycle-attention','offline-saved','api-unavailable']) {
  test('Command Home truthfulness scenario '+scenario,async ({page})=>{
    await home(page,'dark',scenario);
    const state=await page.locator('[data-home-hero-state]').getAttribute('data-home-hero-state');
    if (scenario==='offline-saved' || scenario==='api-unavailable')
      expect(['ready','running'].includes(state||'')).toBe(false);
    await expect(page.getByRole('button',{name:'Workspace details'})).toBeVisible();
  });
}
