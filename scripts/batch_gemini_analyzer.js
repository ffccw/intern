const fs = require('fs');
const path = require('path');
const https = require('https');

const BASE_DIR = path.resolve(__dirname, '..');
const ENV_PATH = path.join(BASE_DIR, '.env');
const DATA_FILE = path.join(BASE_DIR, 'data', 'data.json');
const CSV_FILE = path.join(BASE_DIR, 'data', 'google_sheets_import.csv');

// Load environment variables manually
let apiKey = '';
let modelName = 'gemini-3.8-flash';

if (fs.existsSync(ENV_PATH)) {
  const envContent = fs.readFileSync(ENV_PATH, 'utf8');
  envContent.split('\n').forEach(line => {
    const trimmed = line.trim();
    if (trimmed.startsWith('GEMINI_API_KEY=')) {
      apiKey = trimmed.replace('GEMINI_API_KEY=', '').trim();
    } else if (trimmed.startsWith('GEMINI_MODEL=')) {
      modelName = trimmed.replace('GEMINI_MODEL=', '').trim();
    }
  });
}

if (!apiKey) {
  console.error('[Error] No GEMINI_API_KEY found in .env');
  process.exit(1);
}

console.log(`[Config] Model: ${modelName}, Key: ${apiKey.slice(0, 10)}...`);

function callGeminiAPI(job) {
  return new Promise((resolve, reject) => {
    const prompt = `你是一位專業的科技業招募與管理學院實習顧問。
請嚴格根據以下「104 頁面原始工作內容」分析這份實習職缺，輸出結構化 JSON（繁體中文＋專業英文）。
【重要】job_duties 必須直接對應原始工作內容的真實文字，嚴禁使用罐頭模板或憑標題猜測。

=== 職缺基本資訊 ===
公司名稱：${job.company}
職務名稱：${job.title}

=== 104 頁面原始工作內容（以此為唯一依據） ===
${job.raw_description}

=== 分析規範 (PRD v2 規格) ===
1. job_duties: 從上方原始工作內容中精確提煉 3 點「實習生實際執行的具體工作任務」。
   - 必須與原文對應，不可憑職稱或公司名稱推測
   - 嚴禁罐頭套話（禁止：「日常進度追蹤」、「協助各部門業務」等空泛句子）
   - 每一點必須有具體動作與具體對象
2. job_duties_en: 對應上述 3 點的專業英文翻譯。
3. recommended_courses: 依據工作真實本質，推薦 3~4 門最相關的大學先修課程。
   可選範圍：["人工智慧與商業應用", "商管程式設計 / Python", "資料庫管理", "統計學與數據分析", "供應鏈與運籌管理", "作業管理與製程規劃", "專案管理概論", "行銷管理", "消費者行為", "網路行銷與社群經營", "財務管理", "管理會計學", "人力資源管理", "組織行為學", "資訊安全導論", "作業系統概論", "系統分析與設計", "商務英文溝通與簡報", "企業管理導論", "國際企業經營策略"]
4. jd_summary: 原創雙語摘要（中文 60~100 字，英文 40~60 words）。
5. bilingual_ksa: Knowledge (2項), Skills (2項), Attributes (2項)，每項提供 zh 與 en。
6. trait_advice: 中文特質建議（60 字以內）。
7. trait_advice_en: 英文特質建議。
8. collaborators: 主要跨部門協作對象（2~3 個）。
9. core_dimensions: 各維度權重（合計 100）。
`;

    const payload = JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: {
        temperature: 0.2,
        responseMimeType: 'application/json'
      }
    });

    const url = `https://generativelanguage.googleapis.com/v1beta/models/${modelName}:generateContent?key=${apiKey}`;

    const req = https.request(url, {
      method: 'POST',
      timeout: 25000,
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload)
      }
    }, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        if (res.statusCode === 200) {
          try {
            const data = JSON.parse(body);
            const text = data.candidates[0].content.parts[0].text;
            const parsed = JSON.parse(text);
            resolve(parsed);
          } catch (e) {
            reject(new Error(`Failed to parse JSON response: ${e.message}`));
          }
        } else {
          reject(new Error(`HTTP ${res.statusCode}: ${body.slice(0, 300)}`));
        }
      });
    });

    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Request timed out'));
    });

    req.write(payload);
    req.end();
  });
}

function updateCSV(db) {
  const headers = [
    'job_id', '公司名稱', '股票代號', '成分股指數', '職缺名稱', '實習地點', '實習待遇',
    '條件要求', '工作職責一', '工作職責二', '工作職責三', '建議先修大學課程', '特質建議',
    '104原始連結', 'Dcard避雷連結', 'PTT評價連結', '狀態', '104職缺更新日期', '抓到資料的時間'
  ];

  const escapeCsv = (str) => {
    if (str === null || str === undefined) return '';
    let val = String(str).replace(/"/g, '""');
    if (val.startsWith('=') || val.startsWith('+') || val.startsWith('-') || val.startsWith('@')) {
      val = "'" + val;
    }
    if (val.includes(',') || val.includes('\n') || val.includes('"')) {
      val = `"${val}"`;
    }
    return val;
  };

  const rows = [headers.join(',')];
  db.jobs.forEach(j => {
    const duties = j.job_duties || [];
    const courses = (j.recommended_courses || []).join('、');
    const links = j.community_links || {};
    const dcardUrl = links.dcard_url || '';
    const pttUrl = links.ptt_url || '';

    const row = [
      escapeCsv(j.job_id),
      escapeCsv(j.company),
      escapeCsv(j.stock_code),
      escapeCsv(j.market_category),
      escapeCsv(j.title),
      escapeCsv(j.location),
      escapeCsv(j.salary_desc),
      escapeCsv(j.experience_desc),
      escapeCsv(duties[0] || ''),
      escapeCsv(duties[1] || ''),
      escapeCsv(duties[2] || ''),
      escapeCsv(courses),
      escapeCsv(j.trait_advice || ''),
      escapeCsv(j.url),
      escapeCsv(dcardUrl),
      escapeCsv(pttUrl),
      escapeCsv(j.status || 'open'),
      escapeCsv(j.appear_date || ''),
      escapeCsv(j.scraped_at || '')
    ];
    rows.push(row.join(','));
  });

  const bom = '\uFEFF';
  fs.writeFileSync(CSV_FILE, bom + rows.join('\r\n'), 'utf8');
}

async function run() {
  const db = JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
  const targetJobs = db.jobs.filter(j => j.raw_description && j.raw_description.trim().length > 30);
  console.log(`[Batch] Found ${targetJobs.length} jobs with raw_description to analyze.`);

  let successCount = 0;
  let failCount = 0;

  for (let i = 0; i < targetJobs.length; i++) {
    const job = targetJobs[i];
    console.log(`\n[${i + 1}/${targetJobs.length}] Analyzing: "${job.title}" @ ${job.company}`);

    let parsed = null;
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        parsed = await callGeminiAPI(job);
        break;
      } catch (err) {
        console.warn(`  [Attempt ${attempt}/3] Error: ${err.message}`);
        if (err.message.includes('429')) {
          console.log('  Rate limited (429), waiting 15s before retry...');
          await new Promise(r => setTimeout(r, 15000));
        } else {
          await new Promise(r => setTimeout(r, 4000));
        }
      }
    }

    if (parsed && Array.isArray(parsed.job_duties) && parsed.job_duties.length > 0) {
      job.job_duties = parsed.job_duties;
      if (parsed.job_duties_en) job.job_duties_en = parsed.job_duties_en;
      if (parsed.recommended_courses) job.recommended_courses = parsed.recommended_courses;
      if (parsed.trait_advice) job.trait_advice = parsed.trait_advice;
      if (parsed.trait_advice_en) job.trait_advice_en = parsed.trait_advice_en;
      if (parsed.jd_summary) job.jd_summary = parsed.jd_summary;
      if (parsed.bilingual_ksa) job.bilingual_ksa = parsed.bilingual_ksa;
      if (parsed.collaborators) job.collaborators = parsed.collaborators;
      if (parsed.core_dimensions) job.core_dimensions = parsed.core_dimensions;

      job.ai_model = modelName;
      job.ai_status = 'done';
      successCount++;
      console.log(`  -> SUCCESS! Duties: ${job.job_duties.length}, Courses: ${(job.recommended_courses || []).join(', ')}`);

      // Save incremental checkpoint
      fs.writeFileSync(DATA_FILE, JSON.stringify(db, null, 2), 'utf8');
      updateCSV(db);
    } else {
      failCount++;
      console.error(`  -> FAILED to analyze: ${job.title}`);
    }

    // Rate pacing: 4.5s delay to safely stay below 15 RPM
    if (i < targetJobs.length - 1) {
      await new Promise(r => setTimeout(r, 4500));
    }
  }

  console.log(`\n========================================`);
  console.log(`[Batch Finished] Success: ${successCount}, Failed: ${failCount}`);
  console.log(`Updated files: ${DATA_FILE} & ${CSV_FILE}`);
  console.log(`========================================`);
}

run().catch(console.error);
