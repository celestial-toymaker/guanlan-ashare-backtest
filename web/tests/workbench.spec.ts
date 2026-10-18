import { test, expect } from '@playwright/test';
import fs from 'node:fs';

const shots = '../work/screenshots';
fs.mkdirSync(shots, {recursive:true});

test('实际结果、选股、交易解释、退出与设置', async ({page}) => {
  const errors:string[]=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.setViewportSize({width:1440,height:1060});
  await page.goto('/?run=full-momentum');
  await expect(page.getByRole('heading',{name:'让每一笔收益，都有来处。'})).toBeVisible();
  await expect(page.locator('.metric-value').first()).not.toContainText('10.00 亿');
  await expect(page.locator('.recharts-surface').first()).toBeVisible();
  await page.mouse.move(0,0);
  await expect(page.locator('.period-strip .hint-bubble')).toBeHidden();
  await page.screenshot({path:`${shots}/desktop-overview.png`,fullPage:true});
  await page.getByRole('button',{name:'全市场选股',exact:true}).click();
  await expect(page.locator('tbody tr').first()).toBeVisible();
  await page.getByRole('button',{name:'策略目标',exact:true}).click();
  await expect(page.locator('tbody tr')).toHaveCount(20);
  await page.screenshot({path:`${shots}/desktop-universe.png`,fullPage:true});
  await page.getByRole('button',{name:'交易时间线',exact:true}).click();
  await expect(page.locator('tbody tr').first()).toBeVisible();
  await page.locator('tbody tr').first().click();
  await expect(page.getByRole('dialog',{name:'成交逐笔解释'})).toBeVisible();
  await expect(page.getByText('成交后现金',{exact:true})).toBeVisible();
  await page.screenshot({path:`${shots}/desktop-trade-detail.png`,fullPage:true});
  await page.getByLabel('关闭交易详情').click();
  await page.getByRole('button',{name:'退出计划',exact:true}).click();
  await expect(page.getByRole('heading',{name:'逐证券退出估算'})).toBeVisible();
  await page.screenshot({path:`${shots}/desktop-exits.png`,fullPage:true});
  await page.getByRole('button',{name:/策略实验室/}).click();
  await expect(page.locator('.strategy-card')).toHaveCount(10);
  await page.screenshot({path:`${shots}/desktop-strategies.png`,fullPage:true});
  await page.getByRole('button',{name:'新建回测',exact:true}).click();
  await expect(page.getByRole('dialog',{name:'新建回测'})).toBeVisible();
  await expect(page.locator('.exit-options button')).toHaveCount(3);
  await page.getByLabel('策略',{exact:true}).selectOption('rsi');
  await expect(page.getByLabel('观察窗口（交易日）')).toHaveValue('14');
  await page.getByLabel('关闭设置').click();
  await page.getByRole('button',{name:'策略比较',exact:true}).click();
  await expect(page.getByRole('heading',{name:'放在一起，才看得出差别。'})).toBeVisible();
  expect(errors).toEqual([]);
});

test('手机宽度的导航与结果阅读', async ({page}) => {
  await page.setViewportSize({width:390,height:844});
  await page.goto('/?run=full-momentum');
  await expect(page.getByRole('heading',{name:'让每一笔收益，都有来处。'})).toBeVisible();
  await expect(page.locator('.recharts-surface').first()).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:`${shots}/mobile-overview.png`,fullPage:true});
  await page.getByLabel('展开导航').click();
  await page.getByRole('button',{name:/策略实验室/}).click();
  await expect(page.locator('.strategy-card')).toHaveCount(10);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:`${shots}/mobile-strategies.png`,fullPage:true});
});

test('任务持久化和取消', async ({request}) => {
  const response=await request.post('/api/runs',{data:{name:'浏览器取消流程验收',end:'2025-01-24',auto_sync_status:false}});
  expect(response.status()).toBe(202);
  const job=await response.json();
  await request.post(`/api/runs/${job.id}/cancel`);
  const records=await request.get('/api/runs');
  expect((await records.json()).find((r:any)=>r.id===job.id).status).toBe('cancelled');
});
