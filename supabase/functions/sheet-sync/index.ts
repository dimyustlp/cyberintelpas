import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const jsonHeaders = { "Content-Type": "application/json; charset=utf-8" };
const SOURCE_TYPE = "google_sheet";
const BATCH_SIZE = 100;
const DEFAULT_PUBLIC_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ0-o2qi5vHXxjnwxPAB4wxtAo8ZdmmVjG-wMvOLSXKjNWXOLCyyR0-1F4aOUn9SnFY8NtFvZeSzaft/pub?output=csv";

type SyncCounters = { seen: number; inserted: number; updated: number; skipped: number; failed: number };
type HeaderMap = Record<string, number>;
type ExistingRow = { source_external_id: string | null; content_hash: string | null };

function env(name: string, fallback = ""): string { return Deno.env.get(name)?.trim() || fallback; }
function requiredEnv(name: string): string {
  const value = env(name);
  if (!value) throw new Error(`Edge Function secret belum diisi: ${name}`);
  return value;
}

function parseCsv(text: string): string[][] {
  // Parser RFC-4180 ringan: aman untuk koma, tanda kutip, dan baris baru di dalam sel.
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; }
        else quoted = false;
      } else field += ch;
      continue;
    }
    if (ch === '"') quoted = true;
    else if (ch === ',') { row.push(field); field = ""; }
    else if (ch === '\n') { row.push(field.replace(/\r$/, "")); rows.push(row); row = []; field = ""; }
    else field += ch;
  }
  if (field.length || row.length) { row.push(field.replace(/\r$/, "")); rows.push(row); }
  return rows.filter((r) => r.some((cell) => String(cell || "").trim() !== ""));
}

async function readPublishedCsv(): Promise<string[][]> {
  const url = env("PUBLIC_SHEET_CSV_URL", DEFAULT_PUBLIC_CSV_URL);
  const response = await fetch(url, {
    method: "GET",
    headers: { "User-Agent": "CyberIntelPAS-SheetSync/5.6", "Accept": "text/csv,text/plain,*/*" },
    redirect: "follow",
  });
  if (!response.ok) throw new Error(`CSV publik gagal dibaca: HTTP ${response.status} ${await response.text()}`);
  const text = (await response.text()).replace(/^\uFEFF/, "");
  if (!text.trim()) throw new Error("CSV publik kosong.");
  return parseCsv(text);
}

function normalizeHeader(value: unknown): string { return String(value ?? "").trim().toLowerCase().replace(/\s+/g, " "); }
function resolveColumns(headers: string[]): HeaderMap {
  const aliases: Record<string, string[]> = {
    detected: ["waktu terdeteksi", "tanggal terdeteksi", "waktu deteksi"],
    title: ["judul berita", "judul"],
    media: ["sumber / portal", "sumber/portal", "sumber", "portal", "media"],
    risk: ["tingkat risiko", "risiko", "urgensi"],
    analysis: ["hasil analisis & rekomendasi", "hasil analisis", "analisis & rekomendasi", "analisis"],
    url: ["url / link artikel", "url/link artikel", "link artikel", "url", "link"],
    followup: ["status tindak lanjut", "status tindak lanjut lc", "status tindak lanjut berita"],
    officer: ["petugas respon", "petugas respons", "petugas"],
    responseTime: ["waktu respon", "waktu respons"],
  };
  const result: HeaderMap = {};
  for (const [key, names] of Object.entries(aliases)) {
    result[key] = headers.findIndex((header) => names.some((name) => header === name || header.startsWith(name)));
  }
  for (const required of ["title", "url"]) if ((result[required] ?? -1) < 0) throw new Error(`Kolom wajib tidak ditemukan: ${required}`);
  return result;
}
function cell(row: string[], index: number): string { return index >= 0 ? String(row[index] ?? "") : ""; }
function clean(value: unknown): string { return String(value ?? "").replace(/\s+/g, " ").trim(); }
function cleanMultiline(value: unknown): string { return String(value ?? "").replace(/\r/g, "").trim(); }
function normalizeRisk(value: unknown): string {
  const text = clean(value).toLowerCase();
  if (text.includes("kritis")) return "Kritis";
  if (text.includes("tinggi")) return "Tinggi";
  if (text.includes("sedang")) return "Sedang";
  return "Rendah";
}
function normalizeUrl(value: unknown): string {
  let url = clean(value); if (!url) return ""; if (!/^https?:\/\//i.test(url)) url = `https://${url}`;
  try {
    const parsed = new URL(url);
    const remove = [...parsed.searchParams.keys()].filter((key) => key.toLowerCase().startsWith("utm_") || ["fbclid","gclid","igsh","igshid"].includes(key.toLowerCase()));
    for (const key of remove) parsed.searchParams.delete(key);
    parsed.hash = ""; return parsed.toString().replace(/\/$/, "");
  } catch { return url.replace(/\/$/, ""); }
}
function hostFromUrl(url: string): string { try { return new URL(url).hostname.replace(/^www\./i, ""); } catch { return ""; } }
function detectPlatform(url: string): string {
  const host = hostFromUrl(url).toLowerCase();
  if (host.includes("youtube.com") || host.includes("youtu.be")) return "YouTube";
  if (host.includes("instagram.com")) return "Instagram";
  if (host.includes("facebook.com") || host.includes("fb.watch")) return "Facebook";
  if (host.includes("tiktok.com")) return "TikTok";
  if (host.includes("news.google.com")) return "Google News";
  return "Portal Berita";
}
function parseAnalysis(text: string): { analysis: string; recommendation: string } {
  const analysisMatch = text.match(/ANALISIS\s*:\s*([\s\S]*?)(?:REKOMENDASI\s*:|$)/i);
  const recommendationMatch = text.match(/REKOMENDASI\s*:\s*([\s\S]*)$/i);
  return { analysis: clean(analysisMatch?.[1] || text), recommendation: clean(recommendationMatch?.[1] || "") };
}
function parseDate(value: unknown): string | null {
  const text = clean(value).replace(/\.(?=\d{2}(?:\D|$))/g, ":"); if (!text) return null;
  const match = text.match(/^(\d{1,2})[\/-](\d{1,2})[\/-](\d{4})(?:[,\s]+(\d{1,2})[:.](\d{2}))?/);
  if (match) return new Date(Date.UTC(Number(match[3]), Number(match[2])-1, Number(match[1]), Number(match[4]||0)-7, Number(match[5]||0))).toISOString();
  const parsed = new Date(text); return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
}
function normalizeUptText(value: unknown): string { return clean(value).toLowerCase().replace(/[^a-z0-9]+/g, " ").trim(); }
function matchUpt(text: string, uptNames: { name: string; key: string }[]): string | null {
  const haystack = ` ${normalizeUptText(text)} `;
  for (const item of uptNames) if (item.key && haystack.includes(` ${item.key} `)) return item.name;
  return null;
}
async function sha256(value: string): Promise<string> {
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value)));
  return [...digest].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}
async function fetchAll<T>(queryFactory: (from: number, to: number) => Promise<{ data: T[] | null; error: unknown }>): Promise<T[]> {
  const output: T[] = [];
  for (let from=0;;from+=1000) { const {data,error}=await queryFactory(from,from+999); if(error) throw new Error(JSON.stringify(error)); const batch=data||[]; output.push(...batch); if(batch.length<1000) break; }
  return output;
}

Deno.serve(async (request: Request) => {
  const startedAt = new Date();
  const counters: SyncCounters = { seen:0, inserted:0, updated:0, skipped:0, failed:0 };
  let logId: string | null = null;
  try {
    if (request.method === "OPTIONS") return new Response("ok", { headers: jsonHeaders });
    if (!["POST","GET"].includes(request.method)) return new Response(JSON.stringify({ok:false,message:"Method tidak didukung."}),{status:405,headers:jsonHeaders});
    const expectedToken = requiredEnv("SHEET_SYNC_TOKEN");
    const suppliedToken = request.headers.get("x-sync-token") || new URL(request.url).searchParams.get("token") || "";
    if (suppliedToken !== expectedToken) return new Response(JSON.stringify({ok:false,message:"Token sinkronisasi tidak valid."}),{status:401,headers:jsonHeaders});

    const supabaseUrl = requiredEnv("SUPABASE_URL");
    const serviceRoleKey = requiredEnv("SUPABASE_SERVICE_ROLE_KEY");
    const csvUrl = env("PUBLIC_SHEET_CSV_URL", DEFAULT_PUBLIC_CSV_URL);
    const publicationId = "2PACX-1vQ0-o2qi5vHXxjnwxPAB4wxtAo8ZdmmVjG-wMvOLSXKjNWXOLCyyR0-1F4aOUn9SnFY8NtFvZeSzaft";
    const sheetName = env("GOOGLE_SHEET_NAME", "Sheet1");
    const supabase = createClient(supabaseUrl, serviceRoleKey,{auth:{persistSession:false,autoRefreshToken:false}});
    const triggerType = request.headers.get("x-trigger-type") || "scheduled";
    const {data:logRow,error:logError}=await supabase.from("sheet_sync_log").insert({
      started_at:startedAt.toISOString(),status:"Berjalan",spreadsheet_id:publicationId,sheet_name:sheetName,trigger_type:triggerType,
      metadata:{architecture:"public_csv_pull",function:"sheet-sync",read_only:true,source_url:csvUrl}
    }).select("id").single();
    if(logError) throw new Error(`Gagal membuat log: ${JSON.stringify(logError)}`); logId=logRow.id;

    const values=await readPublishedCsv();
    if(values.length<2){
      await supabase.from("sheet_sync_log").update({finished_at:new Date().toISOString(),status:"Berhasil",message:"Tidak ada baris data.",duration_ms:Date.now()-startedAt.getTime()}).eq("id",logId);
      return new Response(JSON.stringify({ok:true,message:"Tidak ada baris data.",counters}),{headers:jsonHeaders});
    }
    const headers=values[0].map(normalizeHeader); const columns=resolveColumns(headers);
    const uptRows=await fetchAll<{nama_upt:string}>((from,to)=>supabase.from("upt").select("nama_upt").eq("aktif",true).range(from,to));
    const uptNames=uptRows.map(r=>({name:r.nama_upt,key:normalizeUptText(r.nama_upt)})).filter(r=>r.key).sort((a,b)=>b.key.length-a.key.length);
    const existingRows=await fetchAll<ExistingRow>((from,to)=>supabase.from("berita").select("source_external_id,content_hash").eq("source_type",SOURCE_TYPE).not("source_external_id","is",null).range(from,to));
    const existing=new Map(existingRows.map(r=>[r.source_external_id||"",r.content_hash||""]));
    const now=new Date().toISOString(); const payload:Record<string,unknown>[]=[];

    for(let index=1; index<values.length; index++){
      counters.seen++;
      try{
        const row=values[index]||[]; const title=clean(cell(row,columns.title)); const normalizedUrl=normalizeUrl(cell(row,columns.url));
        if(!title&&!normalizedUrl){counters.skipped++;continue;}
        const detected=parseDate(cell(row,columns.detected)); const media=clean(cell(row,columns.media))||hostFromUrl(normalizedUrl)||"Tidak diketahui";
        const risk=normalizeRisk(cell(row,columns.risk)); const rawAnalysis=cleanMultiline(cell(row,columns.analysis)); const parsed=parseAnalysis(rawAnalysis);
        const identityRaw=normalizedUrl||[detected,title,media].join("|"); const externalId=`gs:${await sha256(identityRaw.toLowerCase())}`;
        const contentHash=await sha256([detected,title,media,risk,rawAnalysis,normalizedUrl,cell(row,columns.followup),cell(row,columns.officer),cell(row,columns.responseTime)].join("|"));
        const currentHash=existing.get(externalId); if(currentHash===contentHash){counters.skipped++;continue;}
        if(existing.has(externalId)) counters.updated++; else counters.inserted++;
        const upt=matchUpt(`${title} ${rawAnalysis}`,uptNames);
        payload.push({
          source_record_key:`${SOURCE_TYPE}:${externalId}`,source_type:SOURCE_TYPE,source_external_id:externalId,source_sheet_id:publicationId,source_sheet_name:sheetName,
          source_row_number:index+1,source_updated_at:now,last_synced_at:now,sync_status:"synced",sync_error:"",content_hash:contentHash,
          nama_upt:upt,nama_petugas:"Sinkronisasi Spreadsheet Publik",created_by:"public_csv_sync",link:normalizedUrl,link_normalized:normalizedUrl,
          judul:title||"Tanpa judul",media,platform:detectPlatform(normalizedUrl),tanggal_publikasi:detected,detected_at:detected,kategori:"Lainnya",subkategori:"Umum",
          sentimen:"Tidak diketahui",urgensi:risk,tingkat_perhatian:risk,dampak:"UPT",ringkasan:parsed.analysis||rawAnalysis||title,rekomendasi:parsed.recommendation,
          raw_analysis:rawAnalysis,caption_manual:rawAnalysis,status_baca:"SINKRONISASI OTOMATIS",catatan:upt?"":"Nama UPT belum dikenali otomatis dan perlu dipetakan oleh analis.",
          status_verifikasi:"Belum Ditelaah",ai_provider:"spreadsheet_public_csv",status_tindak_lanjut:clean(cell(row,columns.followup)),petugas_respon:clean(cell(row,columns.officer)),
          waktu_respon:parseDate(cell(row,columns.responseTime)),updated_at:now,
        });
      }catch(rowError){counters.failed++;console.error(`Baris ${index+1}:`,rowError);}
    }
    for(let start=0;start<payload.length;start+=BATCH_SIZE){const batch=payload.slice(start,start+BATCH_SIZE);const {error}=await supabase.from("berita").upsert(batch,{onConflict:"source_record_key",ignoreDuplicates:false});if(error)throw new Error(`Upsert berita gagal: ${JSON.stringify(error)}`);}
    const status=counters.failed>0?"Sebagian":"Berhasil"; const finishedAt=new Date();
    await supabase.from("sheet_sync_log").update({finished_at:finishedAt.toISOString(),status,rows_seen:counters.seen,rows_inserted:counters.inserted,rows_updated:counters.updated,rows_skipped:counters.skipped,rows_failed:counters.failed,duration_ms:finishedAt.getTime()-startedAt.getTime(),message:"Sinkronisasi CSV publik read-only selesai.",metadata:{architecture:"public_csv_pull",rows_payload:payload.length,read_only:true,source_url:csvUrl}}).eq("id",logId);
    return new Response(JSON.stringify({ok:true,message:"Sinkronisasi Spreadsheet publik selesai.",counters}),{headers:jsonHeaders});
  }catch(error){
    const errorText=error instanceof Error?(error.stack||error.message):String(error); console.error(errorText);
    try{if(logId){const supabase=createClient(requiredEnv("SUPABASE_URL"),requiredEnv("SUPABASE_SERVICE_ROLE_KEY"),{auth:{persistSession:false,autoRefreshToken:false}});await supabase.from("sheet_sync_log").update({finished_at:new Date().toISOString(),status:"Gagal",rows_seen:counters.seen,rows_inserted:counters.inserted,rows_updated:counters.updated,rows_skipped:counters.skipped,rows_failed:counters.failed,duration_ms:Date.now()-startedAt.getTime(),message:"Sinkronisasi gagal.",error_detail:errorText.slice(0,10000)}).eq("id",logId);}}catch(logUpdateError){console.error("Gagal memperbarui log kegagalan:",logUpdateError);}
    return new Response(JSON.stringify({ok:false,message:errorText,counters}),{status:500,headers:jsonHeaders});
  }
});
