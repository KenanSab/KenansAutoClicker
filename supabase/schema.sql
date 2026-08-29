-- Kenan's AutoClicker — community preset library
--
-- Run this once in the Supabase SQL editor (Dashboard -> SQL Editor -> New query).
--
-- The security model starts from an uncomfortable fact: the anonymous key is
-- compiled into a desktop application, so it WILL be extracted. Everything here
-- assumes an attacker already has it. The key is therefore given the smallest
-- possible set of rights:
--
--     read    approved presets only
--     insert  into a submission queue it cannot read back
--     insert  reports, which it also cannot read back
--     call    one function that increments an install counter
--
-- It cannot update or delete anything, cannot see pending submissions, and
-- cannot read who reported what. The worst an extracted key achieves is a noisy
-- queue that only the maintainer ever looks at.

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

-- Presets that have been approved and are visible in the app.
create table if not exists public.presets (
    id            uuid primary key default gen_random_uuid(),
    name          text        not null check (char_length(name) between 1 and 60),
    category      text        not null default 'Community'
                              check (char_length(category) <= 24),
    description   text        not null default ''
                              check (char_length(description) <= 220),
    tags          text[]      not null default '{}',
    settings      jsonb       not null,
    author        text        not null default 'unknown'
                              check (char_length(author) <= 40),
    author_id     text,                       -- GitHub user id of the submitter
    installs      integer     not null default 0,
    risky         boolean     not null default false,
    created_at    timestamptz not null default now(),
    hidden        boolean     not null default false,
    report_count  integer     not null default 0
);

-- Anything submitted from the app lands here first and is invisible to users.
create table if not exists public.submissions (
    id            uuid primary key default gen_random_uuid(),
    name          text        not null check (char_length(name) between 1 and 60),
    category      text        not null default 'Community'
                              check (char_length(category) <= 24),
    description   text        not null default ''
                              check (char_length(description) <= 220),
    tags          text[]      not null default '{}',
    settings      jsonb       not null,
    author        text        not null default 'unknown'
                              check (char_length(author) <= 40),
    author_id     text        not null,       -- who signed in to submit it
    status        text        not null default 'pending'
                              check (status in ('pending', 'approved', 'rejected')),
    created_at    timestamptz not null default now()
);

-- Reports raised from inside the app. Write-only from the client's point of view.
create table if not exists public.reports (
    id          uuid primary key default gen_random_uuid(),
    preset_id   uuid        not null references public.presets(id) on delete cascade,
    reason      text        not null default '' check (char_length(reason) <= 200),
    reporter_id text,
    created_at  timestamptz not null default now()
);

create index if not exists presets_visible_idx
    on public.presets (hidden, installs desc);
create index if not exists presets_category_idx
    on public.presets (category);
create index if not exists submissions_status_idx
    on public.submissions (status, created_at desc);

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
alter table public.presets     enable row level security;
alter table public.submissions enable row level security;
alter table public.reports     enable row level security;

-- Anyone may read approved, unhidden presets. That is the entire public surface.
drop policy if exists "read visible presets" on public.presets;
create policy "read visible presets"
    on public.presets for select
    using (hidden = false);

-- No insert, update or delete policy exists for presets, so the anonymous key
-- cannot touch them at all. Approving a preset is done by the maintainer in the
-- dashboard, which bypasses RLS.

-- Signed-in users may submit. There is deliberately no select policy, so a
-- submitter cannot read the queue back, not even their own rows: that keeps the
-- queue useless as a place to publish anything.
drop policy if exists "signed in users may submit" on public.submissions;
create policy "signed in users may submit"
    on public.submissions for insert
    to authenticated
    with check (
        auth.uid() is not null
        and char_length(name) between 1 and 60
        and settings is not null
    );

-- Reports may be raised by anyone, including users who are not signed in, and
-- likewise cannot be read back.
drop policy if exists "anyone may report" on public.reports;
create policy "anyone may report"
    on public.reports for insert
    with check (char_length(reason) <= 200);

-- ---------------------------------------------------------------------------
-- Functions
-- ---------------------------------------------------------------------------

-- Counting installs needs to bump one integer without granting update rights on
-- the table. A security-definer function is the narrow hole for exactly that.
create or replace function public.increment_installs(target uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    update public.presets
       set installs = installs + 1
     where id = target and hidden = false;
end;
$$;

revoke all on function public.increment_installs(uuid) from public;
grant execute on function public.increment_installs(uuid) to anon, authenticated;

-- Reports hide a preset automatically once enough people complain, so abuse is
-- contained between the report arriving and the maintainer reading it. Three is
-- low enough to react quickly and high enough that one angry person cannot
-- silence a rival on their own.
create or replace function public.on_report_added()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    update public.presets
       set report_count = report_count + 1,
           hidden = (report_count + 1) >= 3
     where id = new.preset_id;
    return new;
end;
$$;

drop trigger if exists reports_bump on public.reports;
create trigger reports_bump
    after insert on public.reports
    for each row execute function public.on_report_added();

-- ---------------------------------------------------------------------------
-- Maintainer views
-- ---------------------------------------------------------------------------
-- These are for the Supabase dashboard, which runs as the service role and is
-- not subject to the policies above.

create or replace view public.pending_queue as
    select id, name, category, author, description, tags, settings, created_at
      from public.submissions
     where status = 'pending'
     order by created_at;

create or replace view public.needs_review as
    select id, name, author, report_count, installs, hidden, created_at
      from public.presets
     where report_count > 0
     order by report_count desc;

-- Approving a submission: copy it across and mark it done.
create or replace function public.approve_submission(submission uuid)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    new_id uuid;
begin
    insert into public.presets (name, category, description, tags, settings,
                                author, author_id)
    select name, category, description, tags, settings, author, author_id
      from public.submissions
     where id = submission
    returning id into new_id;

    update public.submissions set status = 'approved' where id = submission;
    return new_id;
end;
$$;

revoke all on function public.approve_submission(uuid) from public;
-- intentionally granted to nobody: run it from the dashboard as the owner
