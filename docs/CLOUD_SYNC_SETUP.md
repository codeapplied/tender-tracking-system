# Cloud sync setup (OneDrive/SharePoint via Microsoft Graph)

Optional. Skip this entirely and the tracker still works — it just stays a
local `.xlsx` file. This is for syncing that file to a shared OneDrive or
SharePoint location so a team can access a live copy.

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
2. Add `Files.ReadWrite.All` (or `Sites.ReadWrite.All` if targeting a
   SharePoint site's document library specifically).
3. Click **Grant admin consent** — application permissions don't work
   without this, and only a tenant admin can do it.

## 4. Find your target drive ID

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

## 5. Set the env vars

```
MS_GRAPH_TENANT_ID=<directory (tenant) ID>
MS_GRAPH_CLIENT_ID=<application (client) ID>
MS_GRAPH_CLIENT_SECRET=<the secret value from step 2>
MS_GRAPH_DRIVE_ID=<the drive ID from step 4>
MS_GRAPH_UPLOAD_PATH=TenderTracker/tenders.xlsx   # path within that drive
```

## 6. Test it

```
tendertracker export
```

Regenerates the local Excel file and, since cloud sync is now configured,
uploads it. If any of the four required vars are missing, cloud sync is
silently skipped (local export still happens) — nothing breaks for someone
who doesn't want this feature.

Note: only a simple upload is implemented (files under 4MB) — plenty for a
tender tracker's Excel file. A resumable upload session would be needed for
anything larger, not built here.
