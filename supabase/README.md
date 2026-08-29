# Community library setup

The app works without any of this. With no backend configured it falls back to
the built-in presets and the static index in `presets/`, which is why none of
the steps below are urgent.

## 1. Create the project

Sign up at [supabase.com](https://supabase.com), create a project, and wait for
it to finish provisioning.

## 2. Create the tables

Dashboard → **SQL Editor** → **New query**, paste all of
[`schema.sql`](schema.sql), and run it. That creates the tables, the row-level
security policies, the install counter, and the report trigger.

## 3. Point the app at it

Dashboard → **Project Settings** → **API**, and copy the project URL and the
`anon` `public` key into `kenansautoclicker/cloud.py`:

```python
SUPABASE_URL = os.environ.get("KAC_SUPABASE_URL", "https://YOURS.supabase.co")
ANON_KEY = os.environ.get("KAC_SUPABASE_ANON_KEY", "eyJ...")
```

### Is it safe to commit that key?

Yes, and it is worth understanding why rather than taking it on faith.

The `anon` key is designed to be public. It identifies the project, it does not
grant trust. Everything it is allowed to do is decided by the row-level security
policies in `schema.sql`, and those give it exactly three abilities:

- read presets that are approved and not hidden
- insert into `submissions`, a table it **cannot read back**
- insert into `reports`, which it also cannot read back
- call `increment_installs`, which changes one integer

It cannot update or delete anything, cannot list pending submissions, and cannot
see who reported what. Someone who pulls the key out of the `.exe` — and they
will, it is a desktop application — gains the ability to put junk in a queue
only you ever look at.

The `service_role` key is the opposite: it bypasses every policy. **Never put it
in the app, in the repository, or in CI.** It belongs only in the dashboard.

## 4. Turn on GitHub sign-in

Needed only for submitting presets; browsing and reporting work without it.

1. Dashboard → **Authentication** → **Providers** → **GitHub** → enable.
2. Register an OAuth app at
   [github.com/settings/developers](https://github.com/settings/developers).
3. Use the callback URL Supabase shows you.
4. Paste the GitHub client ID and secret into Supabase. The secret stays in
   Supabase and never ships with the app.

## 5. Seed it with the existing presets

```bash
python3 tools/seed_library.py --url https://YOURS.supabase.co --key <service_role>
```

Run this once, from your own machine, with the `service_role` key passed as an
argument. It is the one time that key is used, it is never stored, and it never
touches the repository.

## Moderating

Everything is done from the Supabase dashboard, which runs as the owner and so
is not restricted by the policies.

**Approving submissions** — Table Editor → `pending_queue`, then in the SQL
editor:

```sql
select approve_submission('<the submission id>');
```

**Reported presets** — Table Editor → `needs_review`. A preset is hidden
automatically once it reaches three reports.

```sql
-- put it back
update presets set hidden = false, report_count = 0 where id = '<id>';

-- take it down for good
delete from presets where id = '<id>';
```

## Watching the free tier

Dashboard → **Settings** → **Usage**. The free tier gives 500 MB of database and
5 GB of egress per month; a preset is roughly half a kilobyte, so the database
is not the thing to watch. Egress is: every browse downloads the library.

If usage climbs, the client already caches for six hours, and that window can be
widened in `cloud.py` before anything more drastic is needed.
