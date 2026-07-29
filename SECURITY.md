# Security notes

What has been checked, what is deliberately accepted, and where the checks live.

Run `./check.sh` for the automated part. `backend/scripts/isolation.py` is the
one that matters most here: 31 checks that no account can reach another's data
and that nothing answers without a session.

## Enforced

**The signing key.** `.env.example` ships a JWT secret, so any deployment that
never changed it is one where a stranger can mint a token for any user and read
their income, holdings and goals. `ENVIRONMENT=production` now makes the app
refuse to start until `JWT_SECRET` is a real value of at least 32 characters. A
comment saying "change in production" is not a control; the check is in
`Settings`, the only place the value is ever built.

**Account isolation.** Every route that takes an id verifies ownership and
answers 404 rather than 403 to a stranger, so the existence of another user's
goal is not confirmable. Covered by `isolation.py`.

**Input.** Every request body is a Pydantic model with bounds on the numeric
fields. Every query goes through SQLAlchemy; no SQL is built by string.

**Secrets.** No key, token or password is committed. `.env` is ignored and has
never been in the history.

## Accepted, with reasons

**The token lives in `localStorage`.** An httpOnly cookie would survive an XSS
where this does not. Moving it means CSRF protection, cookie-domain handling and
a rewrite of the OAuth callback, which is a Phase 2 change rather than a Phase 1
patch. What reduces the risk today: the app renders no user-supplied HTML
anywhere and uses no `dangerouslySetInnerHTML`, so there is no injection path
into the page.

**react-router 7.18.2 carries a CSRF advisory.** It applies to RSC mode and
server actions. This is a plain Vite SPA using `BrowserRouter` with no server
actions, so the vulnerable path is not reachable. 7.18.2 is the latest published
release and no patched version exists yet. Re-check on the next upgrade.

**No rate limiting.** This is a single-user personal app that is not publicly
deployed. `/research/funds/search` and the ranked stock screen proxy third
parties and would need limits before anyone else can reach them.
