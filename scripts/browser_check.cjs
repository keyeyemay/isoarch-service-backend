// Use a disposable environment only. Install Playwright separately.
const {chromium} = require(process.env.LR3_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  if (process.env.LR3_INTEGRATION !== '1') throw new Error('Set LR3_INTEGRATION=1 for an isolated test server');
  const base = process.env.LR3_BASE_URL || 'http://127.0.0.1:58000';
  const pages = base + '/api/pages/isotopic_signatures';
  const browser = await chromium.launch({headless:true, executablePath:process.env.LR3_CHROME_PATH || undefined});
  const context = await browser.newContext({viewport:{width:430,height:932}});
  await context.route("https://fonts.googleapis.com/**", route => route.abort());
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  fs.mkdirSync('docs/screenshots', {recursive:true});
  try {
    const oldDraft = await context.request.get(base+'/api/services/draft').then(r => r.json());
    if (oldDraft) {
      assert.equal(oldDraft.title, 'Browser verification', 'Do not delete an unrelated existing draft');
      assert.equal((await context.request.delete(base+'/api/services/'+oldDraft.id)).status(), 204);
    }
    await page.goto(pages + '/list');
    await page.screenshot({path:'docs/screenshots/catalog.png',fullPage:true});
    assert.equal(await page.locator('[data-delete="3"]').count(),0);
    await page.fill('#c13_num','-15');
    await Promise.all([page.waitForURL(/c13_max=-15/), page.getByRole('button',{name:'Применить'}).click()]);
    assert.equal(await page.locator('.tile__title').filter({hasText:'Погребение №7'}).count(),0);

    await page.goto(pages + '/draft');
    await page.screenshot({path:'docs/screenshots/create.png',fullPage:true});
    await page.fill('#title','Browser verification');
    await page.setInputFiles('#photo_file',path.resolve('static/images/default_signature.png'));
    await page.setInputFiles('#video_file',path.resolve('static/videos/default_signature.mp4'));
    const created = page.waitForResponse(r => r.url() === base+'/api/services' && r.request().method()==='POST');
    await Promise.all([page.waitForNavigation(),page.getByRole('button',{name:'Далее',exact:true}).click()]);
    const createdResponse = await created;
    assert.equal(createdResponse.status(),201);
    const draft = await context.request.get(base+'/api/services/draft').then(r => r.json());
    await page.screenshot({path:'docs/screenshots/draft.png',fullPage:true});
    await page.fill('#description','Real browser upload and publish');
    await page.fill('#delta_n15','9.4');
    await page.fill('#delta_c13','-18.2');
    await Promise.all([page.waitForURL(new RegExp('/feed/'+draft.id+'$')),page.getByRole('button',{name:'Опубликовать',exact:true}).click()]);
    await page.screenshot({path:'docs/screenshots/feed.png',fullPage:true});
    const like=page.getByRole('button',{name:'Лайк',exact:true});
    await like.click();
    await page.waitForFunction(() => document.querySelector('[data-like]').dataset.liked === '1');
    assert.equal(await page.locator('[data-like-count]').textContent(),'1');
    await like.click();
    await page.waitForFunction(() => document.querySelector('[data-like]').dataset.liked === '0');
    assert.equal(await page.locator('[data-like-count]').textContent(),'0');
    await Promise.all([page.waitForURL(/\/feed\/1$/),page.getByRole('link',{name:'Следующая'}).click()]);

    await page.goto(pages + '/list');
    const deleted = page.waitForResponse(r => r.url()===base+'/api/services/'+draft.id && r.request().method()==='DELETE');
    await Promise.all([page.waitForNavigation(),page.locator(`[data-delete="${draft.id}"]`).click()]);
    assert.equal((await deleted).status(),204);
    assert.equal(await page.locator('.tile__title').filter({hasText:'Browser verification'}).count(),0);
    const hidden=await page.goto(pages+'/feed/'+draft.id);
    assert.equal(hidden.status(),404);
    assert.equal(await page.locator('body').textContent().then(s => s.includes('Browser verification')),false);
    await page.screenshot({path:'docs/screenshots/unavailable.png',fullPage:true});
    assert.deepEqual(errors,[]);
    fs.writeFileSync('docs/browser_verification.json',JSON.stringify({checked_at:new Date().toISOString(),checks:[
      'catalog filter','hide foreign delete','multipart upload','publish redirect','like','unlike',
      'next feed navigation','own soft delete','deleted fields hidden','no browser JavaScript errors'],
      result:'passed',screenshots:'docs/screenshots'},null,2)+'\n');
    console.log('10 browser checks passed; screenshots: docs/screenshots');
  } finally {await browser.close();}
})().catch(error => {console.error(error);process.exitCode=1;});
