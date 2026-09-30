# JurisMon — Supabase & Resend Setup

**Prepared for:** Malok Mading  
**From:** Huzaifah  
**Date:** 30 September 2026

---

There are two accounts left to set up. Both need to be created under your own
email so that you own them outright, which is why they are quicker for you to do
than for me.

Neither takes long. Supabase is about five minutes, Resend about two.

Everything you need to send back is listed at the end of each part, with exactly
where to find it.

> **Please send all values in an attached file**, not typed into the chat. Chat
> messages are stored and searchable, so keys pasted into them should be treated
> as exposed.

---

# Part 1 — Supabase (the database)

This is where every statutory snapshot and every detected change will be stored.

## Step 1 — Create the account

1. Go to **supabase.com**
2. Click **Start your project** (top right)
3. Choose **Continue with Google** and pick the Gmail you want to own this
4. If it asks you to create an organisation, name it `JurisMon` and choose the
   **Free** plan

## Step 2 — Create the project

1. Click **New project**
2. Fill it in:

   | Field | What to enter |
   |---|---|
   | **Name** | `jurismon` |
   | **Database Password** | Click **Generate a password**, then **copy it and save it somewhere safe** |
   | **Region** | **East US (North Virginia)** |
   | **Plan** | Free |

3. Click **Create new project**

> **The database password matters.** Supabase shows it once. You will need it in
> Step 5, and if it is lost the only fix is resetting it. Save it in your
> password manager or the same file you send me.

The project takes about two minutes to finish building. Wait for the green
**Project is healthy** indicator before continuing.

## Step 3 — Get the Project URL and the API key

1. In the left sidebar, click the **gear icon** (Project Settings), at the bottom
2. Click **API**
3. You will see two things to copy:

   - **Project URL** — looks like `https://abcdefghijk.supabase.co`
   - Under **Project API keys**, the row labelled **`service_role`** — click
     **Reveal**, then copy it

> ⚠️ **Copy the `service_role` key, not the `anon` / `public` one.** They sit
> next to each other. The `anon` key is safe to put in a web page and cannot do
> what the application needs; the `service_role` key is the private one.

## Step 4 — Get the connection string

1. Still in **Project Settings**, click **Database**
2. Scroll to **Connection string**
3. Select the **URI** tab
4. Copy the whole line. It looks like:

```
postgresql://postgres:[YOUR-PASSWORD]@db.abcdefghijk.supabase.co:5432/postgres
```

## Step 5 — Replace the password placeholder

The line you just copied contains the literal text `[YOUR-PASSWORD]`. Replace
that, including the square brackets, with the database password from Step 2.

So this:

```
postgresql://postgres:[YOUR-PASSWORD]@db.abcdefghijk.supabase.co:5432/postgres
```

becomes this:

```
postgresql://postgres:YourActualPasswordHere@db.abcdefghijk.supabase.co:5432/postgres
```

> This one catches most people. If the placeholder is left in, the connection
> simply fails and we lose a round trip working out why.

## What to send me from Part 1

Put these three in your file:

```
SUPABASE_URL      = (Step 3 - Project URL)
SUPABASE_KEY      = (Step 3 - the service_role key)
DATABASE_URL      = (Step 5 - the connection string, password filled in)
```

Once I have them I will create the tables, indexes and the full-text search
configuration, and connect the crawler to it. Nothing further is needed from
you for the database.

---

# Part 2 — Resend (email)

You have already created the API key, thank you. One step remains before
JurisMon can actually send from `@jurismon.com`.

## Why

Email providers reject mail that claims to come from a domain it cannot prove it
is allowed to send for. Resend proves it by having you add two DNS records to
`jurismon.com`. Until that is done, anything JurisMon sends is refused.

## Step 1 — Add the domain

1. Go to **resend.com** and sign in
2. Click **Domains** in the left sidebar
3. If `jurismon.com` is not listed, click **Add Domain**, enter `jurismon.com`,
   choose the region closest to you, and click **Add**

## Step 2 — Send me the DNS records

Resend will show a table of records to add — usually a **TXT** record for DKIM
and one for SPF, and sometimes an **MX** record.

You have two options, whichever is easier:

**Option A — send me the records.** Take a screenshot of that table, or copy the
Type, Name and Value of each row into your file. I have DNS access to Cloudflare
already, so I will add them and confirm verification.

**Option B — invite me to Resend.** In Resend, go to **Settings → Team**, invite
**huzaifahnaseer377@gmail.com**, and I will handle the whole thing. This is
slightly better long term, since it lets me check delivery problems without
having to ask you each time.

## What to send me from Part 2

Either the DNS records from Step 2, or a Resend team invitation. Nothing else.

---

# Summary — everything in one place

| # | Item | Where it comes from |
|---|---|---|
| 1 | `SUPABASE_URL` | Supabase → Project Settings → API → Project URL |
| 2 | `SUPABASE_KEY` | Supabase → Project Settings → API → `service_role` key |
| 3 | `DATABASE_URL` | Supabase → Project Settings → Database → Connection string (URI), with the password filled in |
| 4 | Resend DNS records | Resend → Domains → `jurismon.com` — *or* invite me to the Resend team |

That is the last of the account setup. After this everything remaining is on my
side.

---

> **Reminder:** send these in an **attached file**, not typed into the chat.
