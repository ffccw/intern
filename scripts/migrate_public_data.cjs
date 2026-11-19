// One-time migration of public records. Run without --apply to preview changes.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const root = path.resolve(__dirname, '..');
const dataFile = path.join(root, 'data', 'data.json');
const csvFile = path.join(root, 'data', 'google_sheets_import.csv');
const backupDir = path.join(root, 'backup');
const backupFiles = fs.readdirSync(backupDir)
  .filter(name => /^data_backup_\d{8}\.json$/.test(name))
  .sort()
  .map(name => path.join(backupDir, name));
const files = [dataFile, csvFile, ...backupFiles];
const pendingFields = [
  'domain', 'job_duties', 'job_duties_en', 'recommended_courses',
  'trait_advice', 'trait_advice_en', 'bilingual_ksa', 'jd_summary',
  'core_dimensions', 'collaborators', 'project_stages', 'project_stages_en',
  'ai_model',
];
const cannedDuty = '參與軟體模組功能開發、API 介接與系統架構維護作業';
const softwareWords = ['軟體', '開發', '工程師', 'programmer', 'software', 'developer', 'backend', 'frontend', '韌體'];
const csvHeaders = [
  'job_id', '公司名稱', '股票代號', '成分股指數', '專業領域', '實習地區', '職缺名稱', '實習地點',
  '實習待遇', '條件要求', '工作職責一', '工作職責二', '工作職責三',
  '建議先修大學課程', '特質建議', '104原始連結', 'Dcard避雷連結', 'PTT評價連結',
  '狀態', '104職缺更新日期', '抓到資料的時間',
];

function hash(bytes) {
  return crypto.createHash('sha256').update(bytes).digest('hex');
}

function verifiedLinks(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const result = {};
  for (const forum of ['dcard', 'ptt']) {
    const url = value[forum + '_url'];
    if (value[forum + '_verified'] !== true || typeof url !== 'string') continue;
    let parsed;
    try { parsed = new URL(url); } catch { continue; }
    if (parsed.protocol !== 'https:' || parsed.search || parsed.hash) continue;
    const valid = forum === 'dcard'
      ? ['dcard.tw', 'www.dcard.tw'].includes(parsed.hostname) && /^\/f\/[^/]+\/p\/\d+$/.test(parsed.pathname)
      : ['ptt.cc', 'www.ptt.cc'].includes(parsed.hostname) && /^\/bbs\/[^/]+\/M\.\d+\.A\.[A-Za-z0-9]+\.html$/.test(parsed.pathname);
    if (valid) {
      result[forum + '_url'] = url;
      result[forum + '_verified'] = true;
    }
  }
  return result;
}

function sanitizeDocument(document, pendingRaw) {
  if (!document || !Array.isArray(document.jobs)) throw new Error('Invalid jobs document');
  const originalIds = document.jobs.map(job => job.job_id);
  const stats = {jobs: document.jobs.length, rawRemoved: 0, pendingCleaned: 0, linksRemoved: 0};
  for (const job of document.jobs) {
    if (!job || typeof job !== 'object') throw new Error('Invalid job record');
    const oldLinks = job.discussion_links || {};
    job.discussion_links = verifiedLinks(oldLinks);
    if (Object.keys(oldLinks).length && !Object.keys(job.discussion_links).length) stats.linksRemoved++;
    if (!job.education_req || job.education_req.verified !== true) {
      job.education_req = {verified: false};
    }
    if (['大學部在學（學士生實習計畫）', '在學學生（實習計畫）'].includes(job.experience_desc)) {
      job.experience_desc = '';
    }
    const title = String(job.title || '').toLowerCase();
    if ((job.job_duties || []).includes(cannedDuty) && !softwareWords.some(word => title.includes(word))) {
      job.ai_status = 'pending';
    }
    const raw = job.raw_description;
    if (Object.hasOwn(job, 'raw_description')) {
      delete job.raw_description;
      stats.rawRemoved++;
    }
    if (job.ai_status !== 'done') {
      if (pendingRaw && raw && job.job_id) pendingRaw[job.job_id] = raw;
      if (pendingFields.some(field => Object.hasOwn(job, field))) stats.pendingCleaned++;
      for (const field of pendingFields) delete job[field];
    }
  }
  if (document.jobs.some((job, index) => job.job_id !== originalIds[index])) {
    throw new Error('Job identity or order changed');
  }
  if (document.meta?.total_jobs !== document.jobs.length) {
    throw new Error('Job count does not match metadata');
  }
  return stats;
}

function validateDocument(document) {
  const ids = new Set();
  for (const job of document.jobs) {
    if (!job.job_id || ids.has(job.job_id)) throw new Error('Missing or duplicate job ID');
    ids.add(job.job_id);
    if (!/^https:\/\/www\.104\.com\.tw\/job\/[A-Za-z0-9]+$/.test(job.url || '')) {
      throw new Error('Invalid direct 104 URL: ' + job.job_id);
    }
    if (Object.hasOwn(job, 'raw_description')) throw new Error('Source text remains');
    if (job.ai_status !== 'done' && pendingFields.some(field => Object.hasOwn(job, field))) {
      throw new Error('Unverified analysis remains');
    }
    if (job.education_req?.verified !== true && Object.keys(job.education_req || {}).some(key => key !== 'verified')) {
      throw new Error('Unverified education remains');
    }
    if (JSON.stringify(job.discussion_links || {}) !== JSON.stringify(verifiedLinks(job.discussion_links))) {
      throw new Error('Unverified forum link remains');
    }
  }
}

function csvCell(value) {
  const text = String(value ?? '');
  return /[",\r\n]/.test(text) ? '"' + text.replaceAll('"', '""') + '"' : text;
}

function makeCsv(jobs) {
  const rows = [csvHeaders];
  for (const job of jobs) {
    const duties = job.job_duties || [];
    const links = job.discussion_links || {};
    rows.push([
      job.job_id, job.company, job.stock_code, job.index_type, job.domain || '',
      job.region || '', job.title, job.location, job.salary_desc, job.experience_desc,
      duties[0] || '', duties[1] || '', duties[2] || '',
      (job.recommended_courses || []).join('、'), job.trait_advice || '',
      job.url, links.dcard_url || '', links.ptt_url || '',
      job.status, job.appear_date, job.scraped_at,
    ]);
  }
  return Buffer.from('\uFEFF' + rows.map(row => row.map(csvCell).join(',')).join('\r\n') + '\r\n', 'utf8');
}

function atomicReplace(file, bytes) {
  const temporary = file + '.migration-' + process.pid + '.tmp';
  try {
    fs.writeFileSync(temporary, bytes, {flag: 'wx'});
    fs.renameSync(temporary, file);
  } finally {
    if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
  }
}

function main() {
  const args = process.argv.slice(2);
  const apply = args.includes('--apply');
  const archiveIndex = args.indexOf('--archive');
  const archive = archiveIndex >= 0 ? path.resolve(args[archiveIndex + 1] || '') : '';
  if (apply && (!archive || !path.isAbsolute(args[archiveIndex + 1] || ''))) {
    throw new Error('--apply requires an absolute --archive path');
  }
  if (apply && (fs.existsSync(archive) || !path.relative(root, archive).startsWith('..'))) {
    throw new Error('Archive must be new and outside the project');
  }

  const original = new Map(files.map(file => [file, fs.readFileSync(file)]));
  const pendingRaw = {};
  const outputs = new Map();
  const report = {main: null, backups: [], csvRows: 0, pendingRaw: 0};
  const mainDocument = JSON.parse(original.get(dataFile).toString('utf8'));
  report.main = sanitizeDocument(mainDocument, pendingRaw);
  validateDocument(mainDocument);
  outputs.set(dataFile, Buffer.from(JSON.stringify(mainDocument, null, 2), 'utf8'));
  outputs.set(csvFile, makeCsv(mainDocument.jobs));
  report.csvRows = mainDocument.jobs.length;
  for (const file of backupFiles) {
    const document = JSON.parse(original.get(file).toString('utf8'));
    const stats = sanitizeDocument(document, null);
    validateDocument(document);
    report.backups.push({name: path.basename(file), ...stats});
    outputs.set(file, Buffer.from(JSON.stringify(document, null, 2), 'utf8'));
  }
  report.pendingRaw = Object.keys(pendingRaw).length;
  console.log(JSON.stringify(report, null, 2));
  if (!apply) return;

  fs.mkdirSync(path.join(archive, 'original', 'data'), {recursive: true});
  fs.mkdirSync(path.join(archive, 'original', 'backup'), {recursive: true});
  const manifest = [];
  for (const file of files) {
    const relative = path.relative(root, file);
    const destination = path.join(archive, 'original', relative);
    fs.copyFileSync(file, destination);
    const expected = hash(original.get(file));
    if (hash(fs.readFileSync(destination)) !== expected) throw new Error('Archive verification failed: ' + relative);
    manifest.push({file: relative, sha256: expected});
  }
  fs.writeFileSync(path.join(archive, 'pending_raw_descriptions.json'), JSON.stringify(pendingRaw, null, 2), {flag: 'wx'});
  fs.writeFileSync(path.join(archive, 'manifest.json'), JSON.stringify({createdAt: new Date().toISOString(), files: manifest, report}, null, 2), {flag: 'wx'});
  for (const file of files) {
    if (hash(fs.readFileSync(file)) !== hash(original.get(file))) throw new Error('Source changed during migration: ' + file);
  }
  for (const file of files) {
    if (hash(outputs.get(file)) !== hash(original.get(file))) atomicReplace(file, outputs.get(file));
  }
  for (const file of files) {
    if (hash(fs.readFileSync(file)) !== hash(outputs.get(file))) throw new Error('Written file failed verification: ' + file);
  }
  console.log('Migration complete. Original files archived at ' + archive);
}

main();
