# Specra authentication and job-area permissions

This feature branch adds session-based sign-in, administrator-provisioned accounts, and project-scoped roles. It is not active on the deployed service until the changes are reviewed, merged, and deployed with the required environment configuration.

## Security model

- The first administrator is created through a one-time bootstrap. After initialization, public self-registration is enabled by default and can be disabled with ALLOW_PUBLIC_SIGNUP=false. New self-registered accounts always start as viewer; they cannot access any project until an administrator/project owner grants membership.
- Passwords are hashed with scrypt; plaintext passwords are never stored.
- Successful sign-in creates a random session token. Only its SHA-256 hash is stored in SQLite. The browser receives an HttpOnly, SameSite=Lax cookie with a 12-hour lifetime.
- Repeated failed sign-ins for the same normalized email/client host are temporarily locked out.
- Project access requires ownership or an explicit project membership. Knowing a project ID is not sufficient.
- API routes perform authorization checks. Hiding a frontend control is not the authorization boundary.
- The role shown on the account is its default workspace role. A user must still be added to a project to access it; the project role determines their project-specific capabilities.
- Admins manage accounts. Project owners manage membership on their project.

## Public account registration

After the first administrator has been created, logged-out users see **New to Specra? Create an account** if public registration is enabled. Registration requires display name, email, and a password of at least 12 characters. Successful registration returns the user to the sign-in screen with a confirmation message.

- Public registration is enabled by default on a branch using this authentication feature.
- Set `ALLOW_PUBLIC_SIGNUP=false` in the backend environment to restrict account creation to administrators.
- Self-registration grants only the global `viewer` role. It does not grant membership in existing projects or expose project data. The project owner/admin must add the account to a project and assign its project-specific role.
- New accounts are not automatically email-verified in this iteration. Do not use the account as proof of email ownership; add email verification before using this as a production identity system.
- A database-backed attempt limit slows repeated registrations from the same client connection. For higher-traffic production use, move throttling to a dedicated distributed limiter and add email verification.

## Roles

| Role | Intended responsibility |
| --- | --- |
| admin | Workspace administration, account management, and access to all projects. |
| analyst | Create projects, run the full analysis pipeline, refine the brief, and manage project context. |
| planner | Work on planning artifacts and authorized context. |
| architect | Work on architecture artifacts and authorized context. |
| tester | Reserved job-area role for the detailed testing workspace. Test-case generation/execution controls must be added as that workspace is implemented. |
| reviewer | Read project artifacts and review outputs; cannot start a full workflow or mutate project memory by default. |
| developer | Access assigned projects and manage authorized project context; generated-code actions will be added with the coding workspace. |
| viewer | Read-only access to projects they have been assigned. |

The role map is intentionally narrow for this first iteration. When a new action is implemented, add an explicit backend permission and tests for both its allowed and denied cases.

## First local setup

1. Install backend dependencies from the backend directory with: pip install -r requirements.txt.
2. Generate a long, random bootstrap token:

       python -c "import secrets; print(secrets.token_urlsafe(32))"

3. Set the following variables in the backend environment or a local, untracked .env file:

       AUTH_BOOTSTRAP_TOKEN=<paste-the-random-token>
       AUTH_COOKIE_SECURE=false

   Never commit the real token or include it in screenshots/logs. For a production HTTPS deployment, set AUTH_COOKIE_SECURE=true.

4. Start FastAPI and the Vite frontend. Open the workspace; use Initialize Specra for the first time, enter the same bootstrap token, and create the administrator account with a unique email and a password of at least 12 characters.
5. The initial administrator can open Manage accounts to provision accounts and set their default job area. Open a project and use Team to add an existing Specra account and assign its role on that project.

The bootstrap endpoint permanently closes after the first user has been created in that database. If setup needs to be reset, use a deliberate database/admin recovery procedure; do not delete the database as a casual troubleshooting step.

## Hosted deployment requirements

Before enabling this branch on a public deployment:

- Set a high-entropy AUTH_BOOTSTRAP_TOKEN as a server-only secret in the backend hosting dashboard.
- Set AUTH_COOKIE_SECURE=true for HTTPS.
- Use durable storage or a managed database for projects, users, sessions, membership, artifact versions, events, and context. The current SQLite path on an ephemeral filesystem is not adequate for dependable multi-user production.
- Back up and test restore before migrating any existing user/project data.
- Keep all project APIs behind session authorization and verify the cross-user IDOR tests.
- Restrict admin-account provisioning to trusted workspace operators. No API key, bootstrap token, or password belongs in frontend code, Git history, or logs.
- Review login throttling and audit logging under the expected deployment/concurrency model before wide public use.

## Tests

From the backend directory:

    python test_auth_security.py
    python test_auth_routes.py
    python -m compileall -q app test_auth_security.py test_auth_routes.py

CI also builds the frontend. The HTTP tests use a temporary SQLite database and verify that anonymous access is rejected, a project owner can create a project, an assigned reviewer can read but cannot run the pipeline or write project context, and an unassigned account cannot discover a project by its identifier.

## Current limitations

- Password reset by email, MFA, invitation emails, SSO/OIDC, team-level workspaces, and external audit forwarding are not implemented.
- Login throttling currently uses the configured SQLite store, not a distributed rate limiter.
- Project role permissions for the future Tester and Developer workspaces must be expanded when those actions exist.
- This authentication feature branch is not merged or deployed. The currently deployed main branch remains unchanged until reviewed.
