/**
 * CyberIntelPAS — Google Spreadsheet → Supabase
 *
 * Script Properties yang wajib:
 * SUPABASE_URL
 * SUPABASE_SERVICE_ROLE_KEY
 * SPREADSHEET_ID
 * SHEET_NAME
 * SYNC_TOKEN
 *
 * Jalankan setupCyberIntelPasSync() satu kali untuk membuat trigger 5 menit.
 */

const CYPER_SYNC = {
  defaultSpreadsheetId: '1uAA7KfJVnsgUbhKDKfsnYwDYtOEkN1rgsXahbnxPy54',
  defaultSheetName: 'Sheet1',
  sourceType: 'google_sheet',
  batchSize: 100,
};

function setupCyberIntelPasSync() {
  const props = PropertiesService.getScriptProperties();
  if (!props.getProperty('SPREADSHEET_ID')) props.setProperty('SPREADSHEET_ID', CYPER_SYNC.defaultSpreadsheetId);
  if (!props.getProperty('SHEET_NAME')) props.setProperty('SHEET_NAME', CYPER_SYNC.defaultSheetName);

  ScriptApp.getProjectTriggers().forEach(function(trigger) {
    if (trigger.getHandlerFunction() === 'scheduledCyberIntelPasSync') ScriptApp.deleteTrigger(trigger);
  });
  ScriptApp.newTrigger('scheduledCyberIntelPasSync').timeBased().everyMinutes(5).create();
  return 'Trigger 5 menit berhasil dibuat.';
}

function scheduledCyberIntelPasSync() {
  return syncCyberIntelPas_('scheduled');
}

function runCyberIntelPasSyncNow() {
  return syncCyberIntelPas_('manual_editor');
}

function doPost(e) {
  try {
    const body = e && e.postData && e.postData.contents ? JSON.parse(e.postData.contents) : {};
    const expected = getRequiredProperty_('SYNC_TOKEN');
    if (!body.token || body.token !== expected) {
      return jsonOutput_({ok: false, message: 'Token sinkronisasi tidak valid.'});
    }
    const result = syncCyberIntelPas_('manual_webhook');
    return jsonOutput_({ok: true, message: 'Sinkronisasi selesai.', result: result});
  } catch (error) {
    return jsonOutput_({ok: false, message: String(error && error.message || error)});
  }
}

function syncCyberIntelPas_(triggerType) {
  const started = new Date();
  const config = getConfig_();
  const logId = createSyncLog_(config, triggerType, started);
  const counters = {seen: 0, inserted: 0, updated: 0, skipped: 0, failed: 0};

  try {
    const ss = SpreadsheetApp.openById(config.spreadsheetId);
    const sheet = ss.getSheetByName(config.sheetName);
    if (!sheet) throw new Error('Tab tidak ditemukan: ' + config.sheetName);

    const values = sheet.getDataRange().getValues();
    if (values.length < 2) {
      finishSyncLog_(logId, 'Berhasil', counters, started, 'Tidak ada baris data.', '');
      return counters;
    }

    const headers = values[0].map(normalizeHeader_);
    const columns = resolveColumns_(headers);
    validateRequiredColumns_(columns);

    const uptNames = loadUptNames_(config);
    const existingIds = loadExistingExternalIds_(config);
    const payload = [];

    for (let i = 1; i < values.length; i++) {
      counters.seen++;
      try {
        const row = values[i];
        const mapped = mapRow_(row, i + 1, columns, config, uptNames);
        if (!mapped) {
          counters.skipped++;
          continue;
        }
        if (existingIds[mapped.source_external_id]) counters.updated++;
        else counters.inserted++;
        payload.push(mapped);
      } catch (rowError) {
        counters.failed++;
        console.error('Baris ' + (i + 1) + ': ' + rowError);
      }
    }

    for (let start = 0; start < payload.length; start += CYPER_SYNC.batchSize) {
      upsertNews_(config, payload.slice(start, start + CYPER_SYNC.batchSize));
    }

    const status = counters.failed > 0 ? 'Sebagian' : 'Berhasil';
    finishSyncLog_(logId, status, counters, started, 'Sinkronisasi selesai.', '');
    return counters;
  } catch (error) {
    finishSyncLog_(logId, 'Gagal', counters, started, 'Sinkronisasi gagal.', String(error && error.stack || error));
    throw error;
  }
}

function getConfig_() {
  return {
    supabaseUrl: getRequiredProperty_('SUPABASE_URL').replace(/\/$/, ''),
    serviceKey: getRequiredProperty_('SUPABASE_SERVICE_ROLE_KEY'),
    spreadsheetId: PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID') || CYPER_SYNC.defaultSpreadsheetId,
    sheetName: PropertiesService.getScriptProperties().getProperty('SHEET_NAME') || CYPER_SYNC.defaultSheetName,
  };
}

function getRequiredProperty_(name) {
  const value = PropertiesService.getScriptProperties().getProperty(name);
  if (!value) throw new Error('Script Property belum diisi: ' + name);
  return value;
}

function normalizeHeader_(value) {
  return String(value || '').trim().toLowerCase().replace(/\s+/g, ' ');
}

function resolveColumns_(headers) {
  const aliases = {
    detected: ['waktu terdeteksi', 'tanggal terdeteksi', 'waktu deteksi'],
    title: ['judul berita', 'judul'],
    media: ['sumber / portal', 'sumber/portal', 'sumber', 'portal', 'media'],
    risk: ['tingkat risiko', 'risiko', 'urgensi'],
    analysis: ['hasil analisis & rekomendasi', 'hasil analisis', 'analisis & rekomendasi', 'analisis'],
    url: ['url / link artikel', 'url/link artikel', 'link artikel', 'url', 'link'],
    followup: ['status tindak lanjut', 'status tindak lanjut lc', 'status tindak lanjut berita'],
    officer: ['petugas respon', 'petugas respons', 'petugas'],
    responseTime: ['waktu respon', 'waktu respons'],
  };
  const result = {};
  Object.keys(aliases).forEach(function(key) {
    result[key] = -1;
    for (let i = 0; i < headers.length; i++) {
      if (aliases[key].indexOf(headers[i]) !== -1 || aliases[key].some(function(a) { return headers[i].indexOf(a) === 0; })) {
        result[key] = i;
        break;
      }
    }
  });
  return result;
}

function validateRequiredColumns_(columns) {
  ['title', 'url'].forEach(function(key) {
    if (columns[key] < 0) throw new Error('Kolom wajib tidak ditemukan: ' + key);
  });
}

function mapRow_(row, rowNumber, c, config, uptNames) {
  const title = clean_(cell_(row, c.title));
  const url = normalizeUrl_(cell_(row, c.url));
  if (!title && !url) return null;

  const detected = dateToIso_(cell_(row, c.detected));
  const media = clean_(cell_(row, c.media)) || hostFromUrl_(url) || 'Tidak diketahui';
  const risk = normalizeRisk_(cell_(row, c.risk));
  const rawAnalysis = cleanMultiline_(cell_(row, c.analysis));
  const parsed = parseAnalysis_(rawAnalysis);
  const normalizedUrl = normalizeUrl_(url);
  const identityRaw = normalizedUrl || [detected, title, media].join('|');
  const externalId = 'gs:' + sha256_(identityRaw.toLowerCase());
  const contentHash = sha256_([detected, title, media, risk, rawAnalysis, normalizedUrl, cell_(row, c.followup), cell_(row, c.officer), cell_(row, c.responseTime)].join('|'));
  const upt = matchUpt_(title + ' ' + rawAnalysis, uptNames);
  const now = new Date().toISOString();

  return {
    nama_upt: upt || null,
    nama_petugas: 'Sinkronisasi Google Spreadsheet',
    created_by: 'google_sheet_sync',
    link: normalizedUrl,
    link_normalized: normalizedUrl,
    judul: title || 'Tanpa judul',
    media: media,
    platform: detectPlatform_(normalizedUrl),
    tanggal_publikasi: detected,
    detected_at: detected,
    kategori: 'Lainnya',
    subkategori: 'Umum',
    sentimen: 'Tidak diketahui',
    urgensi: risk,
    dampak: 'UPT',
    ringkasan: parsed.analysis || rawAnalysis || title,
    rekomendasi: parsed.recommendation,
    raw_analysis: rawAnalysis,
    caption_manual: rawAnalysis,
    status_baca: 'SINKRONISASI OTOMATIS',
    catatan: upt ? '' : 'Nama UPT belum dikenali otomatis dan perlu dipetakan oleh analis.',
    status_verifikasi: 'Belum Ditelaah',
    tingkat_perhatian: risk,
    ai_provider: 'spreadsheet_source',
    source_type: CYPER_SYNC.sourceType,
    source_external_id: externalId,
    source_sheet_id: config.spreadsheetId,
    source_sheet_name: config.sheetName,
    source_row_number: rowNumber,
    source_updated_at: now,
    last_synced_at: now,
    sync_status: 'synced',
    sync_error: '',
    content_hash: contentHash,
    status_tindak_lanjut: clean_(cell_(row, c.followup)),
    petugas_respon: clean_(cell_(row, c.officer)),
    waktu_respon: dateToIso_(cell_(row, c.responseTime)),
    updated_at: now,
  };
}

function cell_(row, index) {
  return index >= 0 ? row[index] : '';
}

function clean_(value) {
  return String(value == null ? '' : value).replace(/\s+/g, ' ').trim();
}

function cleanMultiline_(value) {
  return String(value == null ? '' : value).replace(/\r/g, '').trim();
}

function normalizeRisk_(value) {
  const v = clean_(value).toLowerCase();
  if (v.indexOf('kritis') !== -1) return 'Kritis';
  if (v.indexOf('tinggi') !== -1) return 'Tinggi';
  if (v.indexOf('sedang') !== -1) return 'Sedang';
  return 'Rendah';
}

function parseAnalysis_(text) {
  const result = {analysis: '', recommendation: ''};
  if (!text) return result;
  const analysisMatch = text.match(/ANALISIS\s*:\s*([\s\S]*?)(?:REKOMENDASI\s*:|$)/i);
  const recommendationMatch = text.match(/REKOMENDASI\s*:\s*([\s\S]*)$/i);
  result.analysis = analysisMatch ? clean_(analysisMatch[1]) : clean_(text);
  result.recommendation = recommendationMatch ? clean_(recommendationMatch[1]) : '';
  return result;
}

function dateToIso_(value) {
  if (!value) return null;
  if (Object.prototype.toString.call(value) === '[object Date]' && !isNaN(value.getTime())) return value.toISOString();
  const text = clean_(value);
  const m = text.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})(?:[,\s]+(\d{1,2}):(\d{2}))?/);
  if (m) {
    return new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]), Number(m[4] || 0), Number(m[5] || 0)).toISOString();
  }
  const parsed = new Date(text);
  return isNaN(parsed.getTime()) ? null : parsed.toISOString();
}

function normalizeUrl_(value) {
  let url = clean_(value);
  if (!url) return '';
  if (!/^https?:\/\//i.test(url)) url = 'https://' + url;
  return url.replace(/[?&](utm_[^=&]+|fbclid|gclid|igsh|igshid)=[^&]*/gi, '').replace(/[?&]$/, '').replace(/\/$/, '');
}

function hostFromUrl_(url) {
  const m = String(url || '').match(/^https?:\/\/([^\/]+)/i);
  return m ? m[1].replace(/^www\./i, '') : '';
}

function detectPlatform_(url) {
  const host = hostFromUrl_(url).toLowerCase();
  if (host.indexOf('youtube.com') !== -1 || host.indexOf('youtu.be') !== -1) return 'YouTube';
  if (host.indexOf('instagram.com') !== -1) return 'Instagram';
  if (host.indexOf('facebook.com') !== -1 || host.indexOf('fb.watch') !== -1) return 'Facebook';
  if (host.indexOf('tiktok.com') !== -1) return 'TikTok';
  if (host.indexOf('news.google.com') !== -1) return 'Google News';
  return 'Portal Berita';
}

function normalizeUptText_(value) {
  return clean_(value).toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

function matchUpt_(text, uptNames) {
  const haystack = ' ' + normalizeUptText_(text) + ' ';
  for (let i = 0; i < uptNames.length; i++) {
    if (haystack.indexOf(' ' + uptNames[i].key + ' ') !== -1) return uptNames[i].name;
  }
  return '';
}

function loadUptNames_(config) {
  const rows = supabaseGetAll_(config, 'upt?select=nama_upt&aktif=eq.true');
  return rows.map(function(r) { return {name: r.nama_upt, key: normalizeUptText_(r.nama_upt)}; })
    .filter(function(r) { return r.key; })
    .sort(function(a, b) { return b.key.length - a.key.length; });
}

function loadExistingExternalIds_(config) {
  const rows = supabaseGetAll_(config, 'berita?select=source_external_id&source_type=eq.google_sheet&source_external_id=not.is.null');
  const set = {};
  rows.forEach(function(r) { if (r.source_external_id) set[r.source_external_id] = true; });
  return set;
}

function supabaseGetAll_(config, path) {
  const output = [];
  for (let start = 0; ; start += 1000) {
    const response = UrlFetchApp.fetch(config.supabaseUrl + '/rest/v1/' + path, {
      method: 'get',
      headers: authHeaders_(config, {'Range': start + '-' + (start + 999)}),
      muteHttpExceptions: true,
    });
    if (response.getResponseCode() >= 300) throw new Error('Supabase GET gagal: ' + response.getContentText());
    const batch = JSON.parse(response.getContentText() || '[]');
    output.push.apply(output, batch);
    if (batch.length < 1000) break;
  }
  return output;
}

function upsertNews_(config, rows) {
  if (!rows.length) return;
  const response = UrlFetchApp.fetch(config.supabaseUrl + '/rest/v1/berita?on_conflict=source_type,source_external_id', {
    method: 'post',
    contentType: 'application/json',
    headers: authHeaders_(config, {'Prefer': 'resolution=merge-duplicates,return=minimal'}),
    payload: JSON.stringify(rows),
    muteHttpExceptions: true,
  });
  if (response.getResponseCode() >= 300) throw new Error('Upsert berita gagal: ' + response.getContentText());
}

function createSyncLog_(config, triggerType, started) {
  const rows = supabaseInsert_(config, 'sheet_sync_log', [{
    started_at: started.toISOString(),
    status: 'Berjalan',
    spreadsheet_id: config.spreadsheetId,
    sheet_name: config.sheetName,
    trigger_type: triggerType,
  }], 'return=representation');
  return rows.length ? rows[0].id : null;
}

function finishSyncLog_(id, status, c, started, message, errorDetail) {
  if (!id) return;
  const config = getConfig_();
  const finished = new Date();
  const payload = {
    finished_at: finished.toISOString(), status: status,
    rows_seen: c.seen, rows_inserted: c.inserted, rows_updated: c.updated,
    rows_skipped: c.skipped, rows_failed: c.failed,
    duration_ms: finished.getTime() - started.getTime(),
    message: message, error_detail: errorDetail,
  };
  const response = UrlFetchApp.fetch(config.supabaseUrl + '/rest/v1/sheet_sync_log?id=eq.' + encodeURIComponent(id), {
    method: 'patch', contentType: 'application/json',
    headers: authHeaders_(config, {'Prefer': 'return=minimal'}),
    payload: JSON.stringify(payload), muteHttpExceptions: true,
  });
  if (response.getResponseCode() >= 300) console.error(response.getContentText());
}

function supabaseInsert_(config, table, rows, prefer) {
  const response = UrlFetchApp.fetch(config.supabaseUrl + '/rest/v1/' + table, {
    method: 'post', contentType: 'application/json',
    headers: authHeaders_(config, {'Prefer': prefer || 'return=minimal'}),
    payload: JSON.stringify(rows), muteHttpExceptions: true,
  });
  if (response.getResponseCode() >= 300) throw new Error('Insert ' + table + ' gagal: ' + response.getContentText());
  return JSON.parse(response.getContentText() || '[]');
}

function authHeaders_(config, extra) {
  const headers = {
    apikey: config.serviceKey,
    Authorization: 'Bearer ' + config.serviceKey,
  };
  Object.keys(extra || {}).forEach(function(k) { headers[k] = extra[k]; });
  return headers;
}

function sha256_(value) {
  const bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, value, Utilities.Charset.UTF_8);
  return bytes.map(function(b) { const v = b < 0 ? b + 256 : b; return ('0' + v.toString(16)).slice(-2); }).join('');
}

function jsonOutput_(payload) {
  return ContentService.createTextOutput(JSON.stringify(payload)).setMimeType(ContentService.MimeType.JSON);
}
