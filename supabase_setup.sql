-- ============================================================
-- LLM & RAG Quiz — Supabase kurulum scripti
-- Supabase Dashboard → SQL Editor → New Query → Çalıştır
-- ============================================================

-- 1. Yanıt tablosu
create table if not exists quiz_answers (
  id             bigserial primary key,
  student_id     text        not null,
  question_index smallint    not null check (question_index between 0 and 4),
  choice_index   smallint    not null,   -- 0-3 = A-D, -1 = süre doldu
  timed_out      boolean     not null default false,
  created_at     timestamptz not null default now()
);

-- 2. Tekrar katılım engeli: aynı öğrenci aynı soruyu iki kez gönderemesin
create unique index if not exists quiz_answers_dedup
  on quiz_answers (student_id, question_index);

-- 3. Row Level Security — anon kullanıcılar insert + select yapabilsin
alter table quiz_answers enable row level security;

create policy "anon insert" on quiz_answers
  for insert to anon with check (true);

create policy "anon select" on quiz_answers
  for select to anon using (true);

-- 4. Realtime aktif et (tablo adını listeye ekle)
-- Dashboard → Database → Replication → quiz_answers → Enable

-- ============================================================
-- Kontrol sorgusu — scriptten sonra çalıştırın
-- ============================================================
select count(*) as satir_sayisi from quiz_answers;
