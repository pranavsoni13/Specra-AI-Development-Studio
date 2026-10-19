# Durable PostgreSQL storage for hosted Specra

Specra uses SQLite by default for local development. Render Free web services have an ephemeral filesystem, so a SQLite file inside the service can disappear on spin-down, restart, or redeploy. That is why a fresh process can show the first-admin setup screen again.

## One-time setup

1. Create a PostgreSQL project with a durable provider. Neon is one option: https://console.neon.tech/
2. In the database dashboard, create or select the database and copy its PostgreSQL connection string. Use a URI that starts with `postgresql://` or `postgres://`; keep the password private.
3. Open the Render dashboard and select the `specra-api-pranavsoni13` web service.
4. Open **Environment** and add or update `DATABASE_URL` with that connection string. Do not put this value in GitHub or paste it in chat.
5. Keep `AUTH_COOKIE_SECURE=true` and keep the existing `AUTH_BOOTSTRAP_TOKEN` secret in Render. Do not regenerate the bootstrap token as a routine workaround.
6. Save the environment change and wait for Render to finish deploying the backend.
7. Open `https://specra-ai-development-studio.vercel.app`. The new PostgreSQL database will initially be empty, so initialize the first admin once in this database using the current `AUTH_BOOTSTRAP_TOKEN` value from Render. Once created, logins and projects should survive backend restarts because the records are stored in PostgreSQL.

After the first admin exists, ordinary people do not need the bootstrap token. With `ALLOW_PUBLIC_SIGNUP=true`, they can choose **New to Specra? Create an account**, make their own credentials, and sign in. New signups start as Viewers and need an administrator to assign project membership.

## Important notes

- The application only uses PostgreSQL after `DATABASE_URL` is set. If it is absent, the backend deliberately retains SQLite for local development; that fallback is not durable on Render Free.
- This change does not migrate a previous SQLite file automatically. The current live site already reports that its first admin is missing, so that instance does not appear to have the old user record available. If a recoverable SQLite backup exists, migrate it before initializing the new admin to preserve projects/users.
- Do not use Render's Free Postgres as a long-term permanent database: Render currently documents that Free Postgres databases expire after 30 days. Check the chosen provider's current limits and backups before relying on it for important data.
- The adapter is intended to support Specra's existing SQL subset; review and run backend tests after the database URL is configured. Keep database credentials server-side.
