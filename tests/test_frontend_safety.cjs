const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'app.js'), 'utf8');
const context = {
  URL,
  console,
  localStorage: { getItem: () => null },
  document: { getElementById: () => null, addEventListener: () => {} },
};
vm.createContext(context);
vm.runInContext(source, context);

const job = {
  job_id: '104_abc123', company: '<img src=x onerror=alert(1)>',
  title: '<script>alert(1)</script>', index_type: '上市', status: 'open',
  location: 'Taipei', salary_desc: 'Negotiable', ai_status: 'done',
  url: 'javascript:alert(1)', appear_date: '2026-11-18',
  job_duties: ['<svg onload=alert(1)>'], recommended_courses: ['<img src=x>'],
  bilingual_ksa: { knowledge: [], skills: [], attributes: [] },
  education_req: { verified: false, level_desc: 'Fabricated degree' },
  discussion_links: { ptt_url: 'https://www.ptt.cc/bbs/Tech_Job/search?q=x', ptt_verified: true },
};
const html = context.renderJobCard(job);
assert.ok(!html.includes('<script>'));
assert.ok(!html.includes('<svg onload'));
assert.ok(!html.includes('href="javascript:'));
assert.ok(!html.includes('Fabricated degree'));
assert.ok(!html.includes('ptt.cc/bbs/Tech_Job/search'));
assert.ok(html.includes('&lt;script&gt;'));

assert.equal(context.safe104JobUrl('https://www.104.com.tw/job/abc123'), 'https://www.104.com.tw/job/abc123');
assert.equal(context.safe104JobUrl('https://evil.example/job/abc123'), '');
assert.equal(context.verifiedForumUrl({ptt_url: 'https://www.ptt.cc/bbs/Tech_Job/M.123.A.abc.html', ptt_verified: true}, 'ptt'), 'https://www.ptt.cc/bbs/Tech_Job/M.123.A.abc.html');
assert.equal(context.verifiedForumUrl({ptt_url: 'https://www.ptt.cc/bbs/Tech_Job/M.123.A.abc.html'}, 'ptt'), '');
const closedDate = (days) => new Date(Date.now() - days * 86400000).toISOString().slice(0, 10);
assert.equal(context.getJobStatusInfo({status: 'closed', closed_date: closedDate(15)}).isArchived, false);
assert.equal(context.getJobStatusInfo({status: 'closed', closed_date: closedDate(31)}).isArchived, true);

const charts = Object.fromEntries(['chart-courses', 'chart-stages', 'chart-dimensions', 'chart-collaborators']
  .map(id => [id, {innerHTML: ''}]));
context.document.getElementById = id => charts[id] || null;
vm.runInContext(`allJobs = ${JSON.stringify([
  {ai_status: 'done', recommended_courses: ['Statistics'], project_stages: [], core_dimensions: [], collaborators: []},
  {ai_status: 'pending', recommended_courses: ['Invented requirement'], project_stages: [], core_dimensions: [], collaborators: []},
])}`, context);
context.renderInsights();
assert.ok(charts['chart-courses'].innerHTML.includes('Statistics'));
assert.ok(!charts['chart-courses'].innerHTML.includes('Invented requirement'));
console.log('Frontend safety checks passed');
