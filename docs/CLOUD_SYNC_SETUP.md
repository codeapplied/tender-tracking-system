# Cloud sync setup (OneDrive/SharePoint + Calendar via Microsoft Graph)

Optional, both features below. Skip this entirely and the tracker still
works — the Excel file just stays local and no calendar events get created.
Covers two independent features sharing the same Azure app registration:
syncing the Excel tracker to OneDrive/SharePoint, and projecting tender
closing dates as Outlook calendar events.

Uses an **app-only (client credentials)** OAuth flow — no user ever signs
in, so it works unattended from a daily cron job. This means it needs its
own Azure AD app registration, not your personal Microsoft account.

## 1. Register an Azure AD app

1. In the [Azure Portal](https://portal.azure.com), go to **Azure Active
   Directory → App registrations → New registration**.
2. Give it any name (e.g. "tender-tracking-system"). Leave redirect URI
   blank — this app never does an interactive login.
3. After creation, note the **Application (client) ID** and **Directory
   (tenant) ID** from the app's Overview page — these are
   `MS_GRAPH_CLIENT_ID` and `MS_GRAPH_TENANT_ID`.

## 2. Create a client secret

1. In the app, go to **Certificates & secrets → New client secret**.
2. Copy the secret **value** immediately — it's only shown once. This is
   `MS_GRAPH_CLIENT_SECRET`.

## 3. Grant API permissions

1. Go to **API permissions → Add a permission → Microsoft Graph →
   Application permissions** (not Delegated — there's no signed-in user).
2. For Excel/OneDrive sync: add `Files.ReadWrite.All` (or
   `Sites.ReadWrite.All` if targeting a SharePoint site's document library
   specifically).
3. For calendar sync: separately add `Calendars.ReadWrite`. Skip this if you
   only want the Excel sync, not calendar events.
4. Click **Grant admin consent** — application permissions don't work
   without this, and only a tenant admin can do it.

## 4. Find your target drive ID (Excel/OneDrive sync only)

The upload target is a specific OneDrive/SharePoint drive, not a personal
`/me/drive` (app-only auth has no signed-in user context). Find it via the
Graph API — e.g. for a specific user's OneDrive:

```
GET https://graph.microsoft.com/v1.0/users/{user-id-or-email}/drive
```

or for a SharePoint site's default document library:

```
GET https://graph.microsoft.com/v1.0/sites/{site-id}/drive
```

Use [Graph Explorer](https://developer.microsoft.com/en-us/graph/graph-explorer)
signed in as an admin to run these and copy the `id` field — that's
`MS_GRAPH_DRIVE_ID`.

## 5. Calendar sync target (calendar sync only)

There's no equivalent "find the ID" step for calendar sync — it targets a
mailbox directly by user ID, UPN, or email address (e.g.
`someone@yourtenant.onmicrosoft.com`). That's `MS_GRAPH_CALENDAR_USER_ID`.
Events get created in that mailbox's default calendar.

## 6. Set the env vars

```
MS_GRAPH_TENANT_ID=<directory (tenant) ID>
MS_GRAPH_CLIENT_ID=<application (client) ID>
MS_GRAPH_CLIENT_SECRET=<the secret value from step 2>

# Excel/OneDrive sync
MS_GRAPH_DRIVE_ID=<the drive ID from step 4>
MS_GRAPH_UPLOAD_PATH=TenderTracker/tenders.xlsx   # path within that drive

# Calendar sync
MS_GRAPH_CALENDAR_USER_ID=<the mailbox to create events in>
```

Each feature is independently optional — set only the vars for the one(s)
you want. Missing vars for a feature just silently skip that feature.

## 7. Test it

```
tendertracker export          # Excel export + cloud sync if configured
tendertracker sync-calendar --apply   # calendar sync
```

If the required vars for a feature are missing, it's silently skipped —
nothing breaks for someone who doesn't want it.

Notes on what's actually implemented: Excel sync only supports a simple
upload (files under 4MB) — plenty for a tender tracker's Excel file; a
resumable upload session would be needed for anything larger, not built
here. Calendar sync diffs against a locally-stored snapshot of what it last
wrote (not a live re-fetch from the Calendar API — see the pipeline module
for why) and creates 1-hour timed events at the closing date/time, not
all-day events.
