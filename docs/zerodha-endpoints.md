# Zerodha endpoint catalogue — from Kite / Console / Coin bundles, 2026-08-27

Method identical to the Groww pass: fetched the three app shells, collected all 12
JS assets they reference (1.25 MB), extracted every API path string literal.
Hosts: `kite.zerodha.com`, `console.zerodha.com`, `coin.zerodha.com`, `api.kite.trade`.
No websocket URLs appear in the bundles (Kite's ticker host is configured at runtime).

**154 distinct paths.**

## Verified working WITHOUT authentication

| Endpoint | Size | What |
|---|---|---|
| `coin.zerodha.com/api/nps/public/fund/performance` | 104 KB | **NPS fund performance, tier1 + tier2.** Every PFM and scheme with `cagr_6_month/1_year/3_year/5_year/since_inception`, `nav`, `nav_date`, `inception_date`, `scheme_type`. Resolves the NPS gap recorded as CONFLICTED in the India-rules note. |
| `coin.zerodha.com/api/nps/public/instruments` | 15 KB | 60 NPS schemes: `fund_code`, `scheme_code`, `asset_category` (E/C/G/A), `ia_min_per`/`ia_max_per` allocation limits, tier. |
| `kite.zerodha.com/api/market-overview` | 16 KB | 247 daily NIFTY closes — one year of daily index history, no auth, no cookie. |
| `api.kite.trade/mf/instruments` | 1.2 MB | 7,600 MF rows. `tradingsymbol` = ISIN, explicit `plan` (direct/regular) and `dividend_type` columns, `purchase_allowed`, `minimum_purchase_amount`. **1,658 direct+growth+purchase_allowed** — the independent cross-check on Groww's 1,686. No TER. |

⚠️ Requesting a Coin/Console path on the wrong host returns that app's HTML shell
with **HTTP 200** (console 6,673 B, coin 1,814 B), not a 404. A caller that trusted
the status code would cache an HTML page as JSON. Check the content type, or that
the body parses, before believing a 200 here.


## PUBLIC — no auth, verified working  (10)

    /api/banner
    /api/instruments/{exchange}/{tradingsymbol}
    /api/kite/bulletins
    /api/market-overview
    /api/nps/public/fund/performance
    /api/nps/public/fund/{fund_code}/nav
    /api/nps/public/instruments
    /api/omnisearch
    /mf/compare
    /oms/bulletins

## AUTH — your login (read-only)  (49)

    /api/marketwatch
    /api/marketwatch/{watchId}
    /api/marketwatch/{watchId}/items
    /api/marketwatch/{watchId}/{itemId}
    /api/mf/allotments
    /api/mf/holdings
    /api/mf/holdings/xirr/portfolio
    /api/mf/holdings/xirr/{isin}
    /api/mf/holdings/{isin}
    /api/nps/users/portfolio
    /api/nps/users/profile
    /api/nudge/mf/orders
    /api/portfolio/holdings/{appName}
    /api/preferences
    /api/preferences/chart
    /api/profile
    /api/tags
    /api/watchlist
    /api/watchlist/{watchlist_id}
    /api/watchlist/{watchlist_id}/{item_id}
    /holdings
    /holdings/all
    /holdings/equity
    /holdings/mutualfund
    /margins
    /oms/charges/orders
    /oms/margins/orders
    /oms/nudge/orders
    /oms/portfolio/holdings
    /oms/portfolio/holdings/all
    /oms/portfolio/holdings/auctions
    /oms/portfolio/holdings/mf
    /oms/portfolio/positions
    /oms/trades
    /oms/user/margins
    /oms/user/margins/{segment}
    /oms/user/profile/full
    /oms/user/profile/vpa
    /oms/user/profile/vpa/validate
    /portfolio/corporate-action-order-window
    /portfolio/holdings
    /portfolio/holdings/discrepancy
    /portfolio/holdings/discrepancy/:segment
    /portfolio/holdings/discrepancy/:segment/:instrument_id
    /portfolio/mtf
    /portfolio/positions
    /portfolio/tags
    /positions
    /profile

## ORDER / MONEY / SESSION — never touched  (62)

    /api/apps/connected
    /api/apps/connected/{appId}
    /api/apps/connected_apps
    /api/apps/connected_apps/{apiKey}
    /api/baskets
    /api/baskets/{basketID}
    /api/baskets/{basketID}/items
    /api/baskets/{basketID}/items/{itemID}
    /api/connect/app/authorize
    /api/connect/basket/orders/{variety}
    /api/connect/session
    /api/handshake/cashier/mandates
    /api/login
    /api/login_reset
    /api/login_reset/validate
    /api/mandates
    /api/mf/holdings/authorise
    /api/mf/mandates/{mandate_id}
    /api/nps/users/contribution
    /api/nps/users/contribution/status
    /api/nps/users/contributions
    /api/nps/users/email/otp
    /api/nps/users/email/otp/verify
    /api/nps/users/initial/contribution
    /api/nps/users/mobile/otp
    /api/nps/users/mobile/otp/verify
    /api/nps/users/register
    /api/otp
    /api/otp/{reqID}
    /api/portfolio/authorise/holdings/{apiKey}/{reqID}
    /api/portfolio/authorise/holdings/{apiKey}/{reqID}/pin
    /api/session
    /api/totp
    /api/twofa
    /api/twofa_reset
    /oms/alerts
    /oms/alerts/{uuid}
    /oms/alerts/{uuid}/history
    /oms/alerts/{uuid}/status
    /oms/bids/instruments
    /oms/bids/orders
    /oms/bids/orders/{type}
    /oms/bids/orders/{type}/{orderID}
    /oms/gtt/triggers
    /oms/gtt/triggers/{orderId}
    /oms/ipo/applications
    /oms/ipo/applications/{id}
    /oms/ipo/instruments
    /oms/ipo/instruments/{id}
    /oms/margins/basket
    /oms/orders
    /oms/orders/{orderId}
    /oms/orders/{orderId}/trades
    /oms/orders/{variety}
    /oms/orders/{variety}/{orderId}
    /oms/portfolio/holdings/authorise
    /oms/trusted/kitefront/user/{userId}/twofa/generate_otp
    /orders/alerts
    /orders/baskets
    /portfolio/holdings/pledge
    /portfolio/holdings/pledge/details
    /portfolio/holdings/transfer

## OTHER  (33)

    /api/captcha
    /api/handshake/cashier/{hash}
    /api/mf/gtt
    /api/mf/gtt/{gtt_id}
    /api/mf/orders
    /api/mf/orders/pending_payment
    /api/mf/orders/{order_id}
    /api/mf/sips
    /api/mf/sips/{sip_id}
    /api/mf/statements/elss/{elss_key}
    /api/mf/stp
    /api/mf/stp/{stp_id}
    /api/mf/swp
    /api/mf/swp/{swp_id}
    /api/nps/users/de-dupe
    /api/nps/users/info
    /api/nps/users/sot
    /api/nps/users/status
    /api/sip
    /api/sip/{sipID}
    /api/sip/{sipID}/skip
    /api/sip/{sipID}/status
    /api/user/app_sessions
    /api/user/avatar
    /api/validate_twofa
    /mf
    /mf/fund/:fundID
    /mf/fund/:fundID/:fundName
    /mf/invest
    /oms/instruments/trigger_range/{transactionType}
    /orders
    /orders/gtt
    /orders/sip

## Notable, beyond the data endpoints

- `/api/mf/holdings/xirr/portfolio` and `/api/mf/holdings/xirr/{isin}` — Zerodha computes XIRR server-side, per portfolio *and* per ISIN. Confirms XIRR-per-holding is a shipped pattern, not an exotic ask.
- `/portfolio/holdings/discrepancy/{segment}/{instrument_id}` — a first-class UI surface for *holdings that disagree with the depository*. No other broker surveyed exposes this.
- `/api/nudge/mf/orders` and `/oms/nudge/orders` — the Nudge system has its own endpoints on both the MF and equity sides, i.e. nudges are computed server-side at order time, not client-side hints.
- `/oms/charges/orders` — a charges calculator keyed to actual orders.
- `/api/mf/gtt` — GTT (good-till-triggered) on *mutual funds*, which Groww does not appear to offer.

