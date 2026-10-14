// Run only against the disposable LR4 verification environment.
const {chromium} = require(process.env.LR4_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  if (process.env.LR4_INTEGRATION !== '1') throw new Error('Set LR4_INTEGRATION=1 for an isolated test server');
  const base = process.env.LR4_BASE_URL || 'http://127.0.0.1:58000';
  const browser = await chromium.launch({headless:true, executablePath:process.env.LR4_CHROME_PATH || undefined});
  const context = await browser.newContext({viewport:{width:430,height:932}});
  await context.route('https://fonts.googleapis.com/**', route => route.abort());
  const page = await context.newPage();
  const errors = [], checks = [];
  page.on('pageerror', error => errors.push(error.message));
  fs.mkdirSync('docs/lr4_screenshots', {recursive:true});
  const screenshot = name => page.screenshot({path:`docs/lr4_screenshots/${name}.png`,fullPage:true});
  try {
    await page.goto(base);
    await page.locator('.tile').first().waitFor();
    await screenshot('catalog');
    assert.equal(await page.locator('[data-delete]').count(), 0);
    await page.evaluate(() => { window.spaVerificationMarker = 'same-document'; });
    await page.fill('[name="c13_max"]', '-15');
    await page.getByRole('button', {name:'Применить'}).click();
    await page.waitForURL(/c13_max=-15/);
    await page.waitForFunction(() => !document.querySelector('#view').hasAttribute('aria-busy'));
    checks.push('Guest catalog, filter, hidden delete buttons');
    await page.getByRole('link', {name:'Добавление',exact:true}).click();
    await page.waitForURL(/#\/auth$/);
    await screenshot('login');
    await page.getByRole('link', {name:'Регистрация',exact:true}).click();
    await page.locator('[data-auth="register"]').waitFor();
    const username = 'browser_' + Date.now();
    await page.fill('[name="username"]', username);
    await page.fill('[name="password"]', 'StudyPassword123');
    await page.getByRole('button', {name:'Зарегистрироваться',exact:true}).click();
    await page.locator('[data-create]').waitFor();
    checks.push('Private route opens login; registration and login return to draft');
    await screenshot('create');
    await page.fill('[name="title"]','LR4 browser verification');
    await page.setInputFiles('[name="image"]',path.resolve('static/images/default_signature.png'));
    await page.setInputFiles('[name="video"]',path.resolve('static/videos/default_signature.mp4'));
    await page.getByRole('button', {name:'Сохранить черновик'}).click();
    await page.locator('[data-publish]').waitFor();
    const id = await page.locator('[data-publish]').getAttribute('data-publish');
    await screenshot('draft');
    await page.fill('[name="description"]','Real browser upload and publish');
    await page.fill('[name="delta_n15"]','9.4');
    await page.fill('[name="delta_c13"]','-18.2');
    await page.getByRole('button',{name:'Опубликовать',exact:true}).click();
    await page.waitForURL(new RegExp('#/feed/'+id+'$'));
    await page.locator('[data-like]').waitFor();
    await page.waitForFunction(() => {
      const video = document.querySelector('.feed__video');
      return video && video.readyState >= 1 && video.duration > 0 && video.duration <= 60;
    });
    await screenshot('feed');
    checks.push('Binary upload, own draft and publication');
    await page.getByRole('link',{name:'Плитка',exact:true}).click();
    await page.locator(`a[href="#/edit/${id}"]`).waitFor();
    await screenshot('own-catalog');
    await page.locator(`a[href="#/edit/${id}"]`).click();
    await page.locator('[data-publish]').waitFor();
    await page.fill('[name="title"]','LR4 edited in browser');
    await page.fill('[name="description"]','Updated after publication');
    await page.fill('[name="delta_n15"]','10.5');
    await page.getByRole('button',{name:'Сохранить изменения',exact:true}).click();
    await page.getByRole('heading',{name:'LR4 edited in browser',exact:true}).waitFor();
    assert.equal(await page.locator('.feed__description').textContent(),'Updated after publication');
    await screenshot('edited');
    checks.push('Author edits published title, description and isotope values through SPA');
    await page.locator('[data-like]').click();
    await page.waitForFunction(() => document.querySelector('[data-like]')?.getAttribute('aria-pressed') === 'true');
    assert.equal(await page.locator('[data-like-count]').textContent(),'1');
    await page.locator('[data-like]').click();
    await page.waitForFunction(() => document.querySelector('[data-like]')?.getAttribute('aria-pressed') === 'false');
    assert.equal(await page.locator('[data-like-count]').textContent(),'0');
    await page.locator('[data-next]').click();
    await page.waitForURL(url => !url.hash.endsWith('/'+id));
    checks.push('Like, unlike and next feed navigation');
    await page.getByRole('link',{name:'Плитка',exact:true}).click();
    await page.locator(`[data-delete="${id}"]`).click();
    await page.waitForFunction(id => !document.querySelector(`[data-delete="${id}"]`) && !document.querySelector('#view').hasAttribute('aria-busy'), id);
    await page.evaluate(id => { location.hash = '#/feed/'+id; }, id);
    await page.getByRole('heading', {name:'Запись недоступна'}).waitFor();
    await screenshot('unavailable');
    assert.equal(await page.locator('#view').textContent().then(s => s.includes('LR4 edited in browser')),false);
    checks.push('Own soft delete and deleted data hidden');
    await page.getByRole('button',{name:'Выйти',exact:true}).click();
    await page.getByRole('link',{name:'Войти',exact:true}).waitFor();
    assert.equal((await context.request.get(base+'/services/draft')).status(),401);
    assert.equal(await page.evaluate(() => window.spaVerificationMarker),'same-document');
    assert.deepEqual(errors,[]);
    checks.push('Logout revokes session; SPA actions keep document; no JavaScript errors');
    const externalRequests = [];
    await page.route('**/*', route => {
      if (!route.request().url().startsWith(base + '/')) {
        externalRequests.push(route.request().url());
        return route.abort();
      }
      return route.continue();
    });
    await page.goto(base + '/docs');
    await page.locator('.swagger-ui .opblock').first().waitFor();
    assert.equal(await page.locator('.swagger-ui .opblock').count(), 12);
    assert.deepEqual(externalRequests, []);
    assert.deepEqual(errors, []);
    await screenshot('swagger');
    checks.push('Swagger renders all 12 methods without external network requests');
    fs.writeFileSync('docs/lr4_browser_verification.json',JSON.stringify({checked_at:new Date().toISOString(),checks,
      result:'passed',screenshots:'docs/lr4_screenshots'},null,2)+'\n');
    console.log(`${checks.length} LR4 browser check groups passed`);
  } catch (error) {
    console.error('URL:', page.url(), 'Notice:', await page.locator('#notice').textContent(), 'JavaScript:', errors);
    await screenshot('failure');
    throw error;
  } finally {await browser.close();}
})().catch(error => {console.error(error);process.exitCode=1;});
