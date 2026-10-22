import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';
// Authored only. No execution during the implementation session.
async function launch(page:Page, scenario='rules-enabled', theme='dark') {
  await page.addInitScript(value=>localStorage.setItem('pocketlab:appearance',value),theme);
  await installScenario(page,scenario);
  await page.goto('/?screen=rules');
  await waitForLiteScreenToSettle(page,'rules');
}
async function manage(page:Page, scenario='rules-enabled', theme='dark') {
  await launch(page,scenario,theme);
  await page.getByRole('button',{name:'Manage Safety Rules'}).click();
  const dialog=page.getByRole('dialog',{name:'Manage Safety Rules'});
  await expect(dialog).toBeVisible();
  return dialog;
}
test.describe('Azure Horizon Rules P0-P4 mocked regression',()=>{
  for(const theme of ['light','dark','system']) {
    test('overview, appearance and Enterprise Manage: '+theme,async({page})=>{
      const dialog=await manage(page,'rules-enterprise-owner',theme);
      await expect(page.locator('.lite-rules-premium-hero')).toHaveCount(1);
      await expect(page.locator('.lite-rules-premium-overview-grid > *')).toHaveCount(2);
      await expect(page.locator('.lite-rules-journey-track > li')).toHaveCount(4);
      const resolved=await page.locator('html').getAttribute('data-lite-theme');
      expect(['light','dark']).toContain(resolved);
      await dialog.getByRole('button',{name:'Policies',exact:true}).click();
      await expect(dialog).toContainText('Policy settings');
      const color=await dialog.evaluate(el=>getComputedStyle(el).backgroundColor);
      expect(color).not.toBe('rgba(0, 0, 0, 0)');
    });
    test('Axe serious/critical Rules and Manage: '+theme,async({page})=>{
      await launch(page,'rules-present',theme);
      const scan=async()=>{
        const output=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
        expect(output.violations.filter(item=>['serious','critical'].includes(item.impact||''))).toEqual([]);
      };
      await scan();
      await page.getByRole('button',{name:'Manage Safety Rules'}).click();
      await scan();
    });
  }
  for(const width of [320,360,375,390,430,700,701,768,1024,1440]) {
    test('200% zoom and responsive Manage at '+width,async({page})=>{
      await page.setViewportSize({width,height:850});
      await launch(page,'rules-premium-long');
      await page.addStyleTag({content:'html { font-size: 200% !important; }'});
      expect(await page.evaluate(()=>document.documentElement.scrollWidth <= document.documentElement.clientWidth+1)).toBe(true);
      await page.getByRole('button',{name:'Manage Safety Rules'}).click();
      const dialog=page.getByRole('dialog',{name:'Manage Safety Rules'});
      await expect(dialog).toHaveAttribute('data-rules-manage-layout',width>=701?'desktop-movable':'mobile-sheet');
      const box=await dialog.boundingBox();
      if(box) expect(box.x+box.width).toBeLessThanOrEqual(width+1);
      if(width<=700) {
        await expect(dialog.getByRole('button',{name:'Move Safety Rules panel'})).toHaveCount(0);
        await expect(dialog.getByRole('button',{name:'Resize Safety Rules panel'})).toHaveCount(0);
        const cols=await page.locator('.lite-rules-journey-track').evaluate(el=>getComputedStyle(el).gridTemplateColumns);
        expect(cols.split(' ').length).toBe(1);
      }
    });
  }
  test('shared desktop move, resize, reset and viewport clamp',async({page})=>{
    await page.setViewportSize({width:1280,height:900});
    const dialog=await manage(page);
    const before=await dialog.boundingBox();
    await dialog.getByRole('button',{name:'Move Safety Rules panel'}).focus();
    await page.keyboard.press('ArrowLeft');
    const moved=await dialog.boundingBox();
    if(before&&moved) expect(moved.x).toBeLessThan(before.x);
    await dialog.getByRole('button',{name:'Resize Safety Rules panel'}).focus();
    await page.keyboard.press('ArrowLeft');
    const resized=await dialog.boundingBox();
    if(moved&&resized) expect(resized.width).toBeLessThanOrEqual(moved.width);
    await dialog.getByRole('button',{name:'Reset Safety Rules panel position and size'}).click();
    await page.setViewportSize({width:760,height:680});
    const clamped=await dialog.boundingBox();
    if(clamped) expect(clamped.x+clamped.width).toBeLessThanOrEqual(761);
    await expect(dialog.getByRole('button',{name:'Close Rules management'})).toBeVisible();
  });
  test('clicking policy form does not drag Manage',async({page})=>{
    await page.setViewportSize({width:1280,height:900});
    const dialog=await manage(page,'rules-enterprise-owner');
    await dialog.getByRole('button',{name:'Policies',exact:true}).click();
    const before=await dialog.boundingBox();
    await dialog.locator('textarea').first().click();
    const after=await dialog.boundingBox();
    if(before&&after) expect(after.x).toBe(before.x);
  });
  test('Journey selection, latest decision and nested insight',async({page})=>{
    await launch(page,'rules-present');
    const stage=page.getByRole('button',{name:/Evaluate:/});
    await stage.focus();await page.keyboard.press('Enter');
    await expect(stage).toHaveAttribute('aria-expanded','true');
    const explain=page.getByLabel('Latest Decision').getByRole('button',{name:'Explain this'});
    if(await explain.count()) {
      await explain.click();
      const detail=page.getByRole('dialog',{name:'Decision Insight'});
      await expect(detail).toContainText('Who requested it?');
      await expect(detail).toContainText('What would change?');
      await expect(detail).toContainText('Why this decision?');
      await expect(detail).toContainText('What can happen next?');
      await expect(detail).toContainText(/execution/i);
    }
  });
  test('Enterprise simulation is never a permission grant',async({page})=>{
    const dialog=await manage(page,'rules-enterprise-owner');
    await dialog.getByRole('button',{name:'Test a Change'}).click();
    await expect(dialog).toContainText('No real permission or system change is granted');
  });
  test('role/capability surfaces use backend reporting',async({page})=>{
    for(const role of ['owner','admin','operator','auditor','viewer']) {
      const dialog=await manage(page,'rules-enterprise-'+role);
      await dialog.getByRole('button',{name:'Policies',exact:true}).click();
      if(role==='viewer') await expect(dialog.getByRole('button',{name:'Create Rules candidate'})).toHaveCount(0);
      await dialog.getByRole('button',{name:'Temporary Access'}).click();
      if(['operator','viewer'].includes(role)) await expect(dialog).toContainText(/not available to this role/i);
      await page.keyboard.press('Escape');
    }
  });
  test('saved/degraded/unavailable never imply ready',async({page})=>{
    for(const scenario of ['rules-validation-error','rules-empty','api-unavailable']) {
      await launch(page,scenario);
      await expect(page.locator('[data-rules-protection-state]')).not.toHaveAttribute('data-rules-protection-state','ready');
    }
  });
  test('reduced motion and focus restoration',async({page})=>{
    await page.emulateMedia({reducedMotion:'reduce'});
    await launch(page,'rules-enabled');
    const trigger=page.getByRole('button',{name:'Manage Safety Rules'});
    await trigger.click();await page.keyboard.press('Escape');
    await expect(trigger).toBeFocused();
    const duration=await page.locator('.lite-rules-journey-track button').first().evaluate(el=>getComputedStyle(el).transitionDuration);
    expect(duration.split(',').every(part=>part.trim()==='0s')).toBe(true);
  });
});
