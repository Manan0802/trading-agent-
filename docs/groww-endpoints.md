# Groww endpoint catalogue — harvested from Groww's own JS bundles, 2026-08-27

Method: fetched 25 Groww route types, collected every `/_next/static/**.js` chunk they
reference (144 distinct, 100 downloaded, 6.5 MB), and extracted every string literal
matching an API path. This is Groww's own client-side route table, not guesswork.

**760 distinct API paths.** Classified below by what they do, because the
classification is the safety boundary: this project never places an order, so the
third group exists to be avoided, not used.

Hosts referenced: groww.in, resources.groww.in, app.groww.in, cms-resources.groww.in,
cmsapi.groww.in, smallcases.groww.in, credit.groww.in, assets-netstorage.groww.in,
security.groww.in, next.groww.in, w.groww.in, 915.groww.in.
Websockets: `wss://groww.in/v1/ws`, `wss://websocket.groww.in`
(socket token endpoint `/v1/api/user/socket/token` returns 401 without auth).

⚠️ `groww.in/robots.txt` carries `Disallow: /v1/api/*`. None of these require
authentication to reach, but reachable is not permitted. Treat as personal-use
research, keep AMFI as the ToS-clean spine, and never make any of this a hard
dependency.


## DATA — no auth needed (read-only)  (131)

    /api/v1/metal-rates/cities
    /api/v1/metal-rates/cities/
    /api/v1/metal-rates/cities/:city
    /api/v1/metal-rates/cities/:city/graph
    /api/v1/metal-rates/country
    /api/v1/metal-rates/country/graph
    /api/v1/metal-rates/country/history
    /api/v1/metal-rates/monthly-movements/
    /api/v1/metal-rates/monthly-movements/:location
    /api/v1/metal-rates/silver/cities
    /api/v1/metal-rates/silver/cities/
    /api/v1/metal-rates/silver/cities/:city
    /api/v1/metal-rates/silver/cities/:city/graph
    /v1/api/charting_service/
    /v1/api/charting_service/v2/chart
    /v1/api/charting_service/v2/chart/{delayed}/exchange/{exchange}/segment/{segment}/{symbol}/all
    /v1/api/charting_service/v2/chart/{delayed}/exchange/{exchange}/segment/{segment}/{symbol}/monthly/v2
    /v1/api/charting_service/v2/chart/{delayed}/exchange/{exchange}/segment/{segment}/{symbol}/{range}
    /v1/api/charting_service/v2/sparkline/aggregated/segment/CASH
    /v1/api/charting_service/v4/chart/exchange/
    /v1/api/charting_service/v4/chart/exchange/{exchange}/segment/CASH/{symbol}
    /v1/api/charting_service/{version}/chart/{delayed}/exchange/{exchange}/segment/{segment}/{symbol}
    /v1/api/commodity_fo/charting_service/
    /v1/api/commodity_fo/charting_service/v2/chart
    /v1/api/commodity_fo/charting_service/v2/chart/{delayed}/exchange/{exchange}/segment/COMMODITY/{code}/monthly/v2
    /v1/api/commodity_fo/charting_service/v2/chart/{delayed}/exchange/{exchange}/segment/COMMODITY/{code}/{range}
    /v1/api/commodity_fo/charting_service/v2/sparkline/aggregated/segment/
    /v1/api/commodity_fo/charting_service/{version}/chart/{delayed}/exchange/{exchange}/segment/{segment}/{symbol}
    /v1/api/data/mf/api/v1/ask/question
    /v1/api/data/mf/api/v1/ask/question/
    /v1/api/data/mf/api/v1/ask/question/search/
    /v1/api/data/mf/api/v1/ask/question/search/{searchId}
    /v1/api/data/mf/api/v1/ask/question/{searchId}/answer
    /v1/api/data/mf/v1/nfo/list
    /v1/api/data/mf/v1/page_content?path=
    /v1/api/data/mf/v1/search/get_schemes_with_prefix
    /v1/api/data/mf/v1/watchlist/user/remove
    /v1/api/data/mf/v1/watchlist/user/scheme
    /v1/api/data/mf/v1/watchlist/user/watch
    /v1/api/data/mf/v1/watchlist/v2
    /v1/api/data/mf/v1/web/content/v2/page/
    /v1/api/data/mf/web/scheme/details
    /v1/api/data/mf/web/v1/collection
    /v1/api/data/mf/web/v1/collections/
    /v1/api/data/mf/web/v1/custom/content
    /v1/api/data/mf/web/v1/fetch/fund_news/
    /v1/api/data/mf/web/v1/groww_popular_funds
    /v1/api/data/mf/web/v1/scheme/
    /v1/api/data/mf/web/v1/scheme/portfolio/
    /v1/api/data/mf/web/v1/scheme/search/
    /v1/api/data/mf/web/v1/similar/scheme/top
    /v1/api/data/mf/web/v4/scheme/meta_data
    /v1/api/data/mf/web/v5/scheme/search/
    /v1/api/data/mf/web/v6/scheme/search/
    /v1/api/equity/data/v1/client/stocks/technicals/summary/search_id/
    /v1/api/equity/data/v1/client/stocks/technicals/summary/search_id/{searchId}
    /v1/api/equity/data/v1/client/stocks/volume/summary/search_id/
    /v1/api/equity/data/v1/client/stocks/volume/summary/search_id/{searchId}
    /v1/api/equity/data/v1/shareholding-patterns/holders/
    /v1/api/equity/data/v1/shareholding-patterns/holders/{gsin}
    /v1/api/search/v3/query/
    /v1/api/search/v3/query/feature_search/st_fs
    /v1/api/search/v3/query/filter_derived_data/st_filter
    /v1/api/search/v3/query/global/st_p_query
    /v1/api/search/v3/query/global/st_query
    /v1/api/search/v3/query/mf_prime_screener/st_prime
    /v1/api/stocks_data/equity_feature/v2/company/corporate_action/event
    /v1/api/stocks_data/equity_feature/v2/company/corporate_action/event?gsin=
    /v1/api/stocks_data/explore/v2/indices/
    /v1/api/stocks_data/explore/v2/indices/market_trends/filters
    /v1/api/stocks_data/explore/v2/indices/{growwIndexId}/market_trends
    /v1/api/stocks_data/v1/
    /v1/api/stocks_data/v1/accord_company/isin/
    /v1/api/stocks_data/v1/accord_company/isin/{isin}/minimal
    /v1/api/stocks_data/v1/accord_points/exchange/
    /v1/api/stocks_data/v1/accord_points/exchange/{exchange}/segment/{segment}/latest_indices_ohlc/{symbol}
    /v1/api/stocks_data/v1/accord_points/exchange/{exchange}/segment/{segment}/latest_prices_ohlc/{symbol}
    /v1/api/stocks_data/v1/aggregated_stocks_market_today
    /v1/api/stocks_data/v1/alerts/custom
    /v1/api/stocks_data/v1/all_stocks
    /v1/api/stocks_data/v1/all_stocks/filtersV2
    /v1/api/stocks_data/v1/company/
    /v1/api/stocks_data/v1/company/{idType}/{id}
    /v1/api/stocks_data/v1/company/{idType}/{searchId}
    /v1/api/stocks_data/v1/company/{idType}/{searchId}/financial_statements
    /v1/api/stocks_data/v1/etfs
    /v1/api/stocks_data/v1/fundamentals/
    /v1/api/stocks_data/v1/fundamentals/{product}/info
    /v1/api/stocks_data/v1/global_instruments
    /v1/api/stocks_data/v1/market/market_timing
    /v1/api/stocks_data/v1/tr_live_book/exchange/
    /v1/api/stocks_data/v1/tr_live_book/exchange/{exchange}/segment/{segment}/{symbol}/latest
    /v1/api/stocks_data/v1/tr_live_delayed_prices/exchange/
    /v1/api/stocks_data/v1/tr_live_delayed_prices/exchange/{exchange}/segment/{segment}/{symbol}/latest
    /v1/api/stocks_data/v1/tr_live_indices/exchange/
    /v1/api/stocks_data/v1/tr_live_indices/exchange/{exchange}/segment/{segment}/{symbol}/latest
    /v1/api/stocks_data/v1/tr_live_prices/exchange/
    /v1/api/stocks_data/v1/tr_live_prices/exchange/US/latest_prices_batch
    /v1/api/stocks_data/v1/tr_live_prices/exchange/{exchange}/segment/{segment}/{symbol}/latest
    /v1/api/stocks_data/v1/{livePoint}/segment/CASH/latest_aggregated
    /v1/api/stocks_data/v2/explore/list/top
    /v1/api/stocks_fo_data/
    /v1/api/stocks_fo_data/v1/charting_service
    /v1/api/stocks_fo_data/v1/charting_service/chart/spark_line_prices
    /v1/api/stocks_fo_data/v1/charting_service/{delayed}/chart/exchange/{exchange}/segment/{segment}/{symbol}/{range}
    /v1/api/stocks_fo_data/v1/contracts/
    /v1/api/stocks_fo_data/v1/contracts/{searchId}/top
    /v1/api/stocks_fo_data/v1/derivatives/
    /v1/api/stocks_fo_data/v1/derivatives/{searchId}/contract
    /v1/api/stocks_fo_data/v1/live-aggregations/explore/market_trends/instrument/
    /v1/api/stocks_fo_data/v1/live-aggregations/explore/market_trends/instrument/{instrument}
    /v1/api/stocks_fo_data/v1/nearest_expiries
    /v1/api/stocks_fo_data/v1/tr_live_book/exchange/
    /v1/api/stocks_fo_data/v1/tr_live_book/exchange/{exchange}/segment/{segment}/{symbol}/latest
    /v1/api/stocks_fo_data/v1/tr_live_prices/exchange/
    /v1/api/stocks_fo_data/v1/tr_live_prices/exchange/{exchange}/segment/FNO/latest_prices_batch
    /v1/api/stocks_fo_data/v1/tr_live_prices/exchange/{exchange}/segment/FNO/{contractId}/latest
    /v1/api/stocks_fo_data/{version}/charting_service/{delayed}/chart/exchange/{exchange}/segment/{segment}/{symbol}
    /v1/api/stocks_primary_market_data/v1/ipo/company/
    /v1/api/stocks_primary_market_data/v1/ipo/company/{searchId}
    /v1/api/stocks_primary_market_data/v1/sgb/aggregated
    /v1/api/stocks_primary_market_data/v2/ipo/all
    /v1/api/stocks_primary_market_data/v3/summary
    /v1/api/us_stocks_data/v1/company/all
    /v1/api/us_stocks_data/v1/company/details
    /v1/api/us_stocks_data/v1/company/filters
    /v1/api/us_stocks_data/v1/company/financial/search_id/
    /v1/api/us_stocks_data/v1/company/financial/search_id/{searchId}
    /v1/api/us_stocks_data/v1/company/popular_stocks
    /v1/api/us_stocks_data/v1/company/search_id/
    /v1/api/us_stocks_data/v1/company/search_id/{searchId}

## AUTH — needs your login (read-only, portfolio)  (198)

    /api/v1/bankingpages/
    /api/v1/bankingpages/{slug}
    /api/v1/login/check_email
    /api/v1/login/user
    /api/v1/logout/user
    /api/v1/register_device/send_otp
    /api/v1/register_device/validate_otp
    /api/v2/auth/check/pin_status
    /api/v2/auth/validate/pin
    /v1/api/aggregator/v1/holdings/scheme
    /v1/api/aggregator/v4/dashboard
    /v1/api/apex/oauth2/v1/authorize
    /v1/api/api/cc/v1/groww/notification/user
    /v1/api/api/cc/v1/groww/notification/user/viewed
    /v1/api/bank_mandate/v1/extended/create_mandate
    /v1/api/bank_mandate/v1/initiated_mandate
    /v1/api/bank_mandate/v2/bank/
    /v1/api/bank_mandate/v2/bank/client/all_bank
    /v1/api/bank_mandate/v2/bank/client/edit/bank
    /v1/api/bank_mandate/v2/bank/client/edit/bank?bank_id=
    /v1/api/bank_mandate/v2/bank/client/update_default_bank
    /v1/api/bank_mandate/v2/bank/client/update_default_bank?bank_id=
    /v1/api/bank_mandate/v2/extended/create_mandate
    /v1/api/commodity/v1/holding/list
    /v1/api/commodity/v1/onboarding/commodity_onboarding_status
    /v1/api/commodity/v2/positions
    /v1/api/commodity_fo/commodity/oms_rms/v1/exchange/{exchange}/contract/{contractId}/user-info
    /v1/api/commodity_fo/commodity_router/v1/positions
    /v1/api/doc/user/v1/check_upload_status
    /v1/api/doc/user/v1/download/user/get_mandate_pdf
    /v1/api/doc/user/v1/get_upload_token
    /v1/api/dp/userpref/preference/fno_kill_switch
    /v1/api/dp/userpref/preference/fno_trading_preferences
    /v1/api/dp/userpref/preferences
    /v1/api/fno/smart-exit/v1/user/limit
    /v1/api/fno/smart-exit/v2/user/limit
    /v1/api/fno/v2/oms/rms/exchange/{exchange}/contract/{contractId}/user-info
    /v1/api/growth/v2/messageboards
    /v1/api/groww_mandate/v2/bank-mandate
    /v1/api/helpsupport/v1/inapp/notification/mark_seen
    /v1/api/helpsupport/v1/ticket/validate_request
    /v1/api/helpsupport/v1/ticket/view/all_tickets
    /v1/api/helpsupport/v1/voice_call
    /v1/api/helpsupport/v1/voice_call/call_me_back/time
    /v1/api/helpsupport/v1/voice_call/call_me_back?questionId=
    /v1/api/helpsupport/v3/userfeedback
    /v1/api/helpsupport/v5/question
    /v1/api/helpsupport/v5/question/
    /v1/api/helpsupport/v5/question/{questionId}/answer
    /v1/api/helpsupport/v6/main_page/response?page=0&size=3&scrollType=DESC&keys=segments
    /v1/api/invest/margin/x/aggregator/v1/p0/balance/details
    /v1/api/margin_advance/v1/margin/user_margin_details
    /v1/api/margin_advance/v2/margin/user_margin_details
    /v1/api/mf/prime/v1/collections/
    /v1/api/mf/prime/v1/config/meta_data
    /v1/api/mf/prime/v1/portfolio/dashboard
    /v1/api/mf/prime/v1/scheme/read?search_id=
    /v1/api/mf/prime/v1/sip/
    /v1/api/mf/prime/v1/sip/all
    /v1/api/mf/prime/v1/sip/cancelled
    /v1/api/mf/user/subscription
    /v1/api/onboarding/doc_upload/v2/poll
    /v1/api/onboarding/us-stocks/activate
    /v1/api/portfolio/track/cas/request?request_id=
    /v1/api/portfolio/track/submit/qr
    /v1/api/portfolio/v1/folio_holdings/validate_purchase_order
    /v1/api/portfolio/v1/nominee/eligibleFolios/details
    /v1/api/portfolio/v1/nominee/update
    /v1/api/portfolio/v1/nominee/verify
    /v1/api/portfolio/v1/track/snapshot/delete?scheme_code=
    /v1/api/portfolio/v1/transaction/get_amount_available_to_redeem_for_elss
    /v1/api/preference/v1/get_preference
    /v1/api/preference/v1/set_preference
    /v1/api/presentation/v2/watchlist/
    /v1/api/presentation/v2/watchlist/aggregated
    /v1/api/presentation/v2/watchlist/{wlId}/details
    /v1/api/primaries/v1/equity-blocking/primary/user/status
    /v1/api/selection/v2/watchlist
    /v1/api/selection/v2/watchlist/
    /v1/api/selection/v2/watchlist/all/items_mapping
    /v1/api/selection/v2/watchlist/item
    /v1/api/selection/v2/watchlist/{watchlistId}
    /v1/api/stocks/v1/authentication/edis/generate_tpin
    /v1/api/stocks/v1/equity-blocking/etf-nfo/user/status
    /v1/api/stocks/v1/equity-blocking/user/status
    /v1/api/stocks/v1/position/convert/multi
    /v1/api/stocks/v1/sip/dashboard/active
    /v1/api/stocks/v1/sip/dashboard/active/count
    /v1/api/stocks/v1/sip/dashboard/active/count/gsin/all
    /v1/api/stocks/v1/sip/dashboard/details/
    /v1/api/stocks/v1/sip/dashboard/details/{sipId}
    /v1/api/stocks/v1/sip/dashboard/message
    /v1/api/stocks_fo/stocks/margin/advance/v1/spanexposure
    /v1/api/stocks_fo/stocks/margin/v1/approx-required
    /v1/api/stocks_fo/stocks/margin/v2/approx-required
    /v1/api/stocks_fo/stocks_router/v1/dashboard
    /v1/api/stocks_fo/stocks_router/v1/dashboard?ts=
    /v1/api/stocks_fo/stocks_router/v1/positions
    /v1/api/stocks_fo/stocks_router/v4/dashboard
    /v1/api/stocks_fo/stocks_router/v4/dashboard?ts=
    /v1/api/stocks_portfolio/v2/holding/symbol_isin/
    /v1/api/stocks_portfolio/v2/holding/symbol_isin/{symbolIsin}/txns/unrealized
    /v1/api/stocks_router/v4/holding
    /v1/api/stocks_router/v4/holding/symbol_isin/
    /v1/api/stocks_router/v4/holding/symbol_isin/{symbolIsin}
    /v1/api/stocks_router/v5/dashboard/positions
    /v1/api/stocks_router/v6/dashboard
    /v1/api/stocks_router/v6/dashboard?ts=
    /v1/api/us/stocks/portfolio/holdings
    /v1/api/us/stocks/trading/margins
    /v1/api/us_stocks/v1/banks/list
    /v1/api/us_stocks/v1/events/user/interested/send_confirmation
    /v1/api/us_stocks/v1/portfolio
    /v1/api/us_stocks/v1/portfolio/
    /v1/api/us_stocks/v1/portfolio/:symbol
    /v1/api/us_stocks/v1/user/balance
    /v1/api/us_stocks/v1/user/bank/added
    /v1/api/us_stocks/v1/user/bank/available
    /v1/api/us_stocks/v1/user/bank/link
    /v1/api/us_stocks/v1/user/bank/primary
    /v1/api/us_stocks/v1/user/bank/swift/update
    /v1/api/us_stocks/v1/user/fund/a2
    /v1/api/us_stocks/v1/user/fund/a2/confirm
    /v1/api/us_stocks/v1/user/fund/init
    /v1/api/us_stocks/v1/user/ledger
    /v1/api/us_stocks/v1/users/email/funding_instructions
    /v1/api/us_stocks/v1/users/onboard/status
    /v1/api/us_stocks/v2/portfolio
    /v1/api/us_stocks/v2/portfolio/
    /v1/api/us_stocks/v2/portfolio/:symbol
    /v1/api/user/auth/signup/gmail
    /v1/api/user/core/auth/login/email
    /v1/api/user/core/auth/login/gmail
    /v1/api/user/mtf/position-convert/cancel
    /v1/api/user/mtf/position-convert/create
    /v1/api/user/mtf/position-details
    /v1/api/user/socket/token
    /v1/api/user/v1/auth/logged_in_sessions
    /v1/api/user/v1/auth/logout
    /v1/api/user/v1/auth/logout/session
    /v1/api/user/v1/auth/pin/create
    /v1/api/user/v1/auth/pin/send_otp?resendFlag=false
    /v1/api/user/v1/auth/pin/send_otp?resendFlag=true
    /v1/api/user/v1/auth/pin/update
    /v1/api/user/v1/auth/pin/validate_auth_id
    /v1/api/user/v1/auth/token/refresh
    /v1/api/user/v1/bank/
    /v1/api/user/v1/bank/{bankId}
    /v1/api/user/v1/doc_ref
    /v1/api/user/v1/email/verification/link/
    /v1/api/user/v1/external/create
    /v1/api/user/v1/family_account
    /v1/api/user/v1/investment/event?investment_event_sent=true
    /v1/api/user/v1/login/change_pwd
    /v1/api/user/v1/login/reset/otp
    /v1/api/user/v1/onboarding/pincode
    /v1/api/user/v1/preference/product_list
    /v1/api/user/v1/preference/product_types
    /v1/api/user/v1/preference/update_preference_parameters
    /v1/api/user/v1/register/attributes
    /v1/api/user/v1/register/config/pincode/
    /v1/api/user/v1/register/device/otp/send
    /v1/api/user/v1/register/device/otp/validate
    /v1/api/user/v1/register/email/init
    /v1/api/user/v1/register/email/validate
    /v1/api/user/v1/register/email/verification
    /v1/api/user/v1/register/email_otp/send
    /v1/api/user/v1/register/email_otp/validate
    /v1/api/user/v1/register/new/mobile_number
    /v1/api/user/v2
    /v1/api/user/v2/auth/pin/send_otp
    /v1/api/user/v2/auth/pin/send_otp?resendFlag=
    /v1/api/user/v2/auth/pin/send_otp?resendFlag=false
    /v1/api/user/v2/auth/pin/send_otp?resendFlag=true
    /v1/api/user/v2/auth/pin/validate
    /v1/api/user/v2/auth/pin_status
    /v1/api/user/v2/login/check_email
    /v1/api/user/v2/login/masked_email
    /v1/api/user/v2/register
    /v1/api/user/v2/send/app_link_sms
    /v1/api/user/v2/send/app_link_sms?mobile_number=
    /v1/api/user/v3/attributes
    /v1/api/user/v3/register/validate/new_mobile
    /v1/api/user/v3/register/validate/new_mobile?link=
    /v1/api/wallet/v1/account
    /v1/api/wallet/v1/txn_details/fetch
    /v1/api/wallet/v1/txn_details/settlement/charges
    /v1/api/wallet/v1/txn_details/settlement/charges?transactionId=
    /v1/api/wallet/v1/txn_details/settlement/fetch
    /v1/api/wallet/v1/txn_details/settlement/fno/fetch
    /v1/api/wallet/v2/account/update/authorisation
    /v1/api/wallet/v2/account/update/authorisation?quarterly_settlement_type=
    /v1/api/wallet/v3/cf_ledger/download
    /v1/api/wallet/v3/credit_pending
    /v1/api/wallet/v4/ledger
    /v1/api/wallet/v4/ledger/txn
    /v1/api/wallet/v5/ledger/txn
    /v1/api/wallet/v6/filter_ledger

## ORDER / MONEY — never touched  (258)

    /v1/api/advance-orders/equity/orders/v1/gtt
    /v1/api/advance-orders/equity/orders/v1/gtt/
    /v1/api/advance-orders/equity/orders/v1/gtt/order/
    /v1/api/advance-orders/equity/orders/v1/gtt/order/{gttOrderId}
    /v1/api/advance-orders/equity/orders/v1/gtt/{gttOrderId}
    /v1/api/advance-orders/equity/orders/v1/gtt/{gttOrderId}/cancel
    /v1/api/aggregator/v1/mf/order/track/
    /v1/api/bank_mandate/v2/bank/{bankId}/mandate_type
    /v1/api/bff/invest_money/v1/withdrawable_balance
    /v1/api/bonds-rfq/v1/order
    /v1/api/bse/v1/bank/config/list/supported/mandate
    /v1/api/cart/v1/cart/
    /v1/api/cart/v1/cart?
    /v1/api/cart/v1/create_bulk
    /v1/api/checkout/v1/
    /v1/api/checkout/v4/
    /v1/api/checkout/v4/request
    /v1/api/checkout/v5/
    /v1/api/checkout/v5/request
    /v1/api/checkout/v5/{checkoutId}/status
    /v1/api/commodity/orderTrack
    /v1/api/commodity/v1/order/filter
    /v1/api/commodity/v1/order/search
    /v1/api/commodity/v2/order
    /v1/api/commodity_fo/commodity/v1/order
    /v1/api/commodity_fo/commodity/v1/order/detail/groww_order_id/
    /v1/api/commodity_fo/commodity/v1/order/detail/groww_order_id/{growwOrderId}
    /v1/api/commodity_fo/commodity/v1/order/groww_order_id/
    /v1/api/commodity_fo/commodity/v1/order/groww_order_id/{growwOrderId}/cancel
    /v1/api/commodity_fo/commodity/v1/order/groww_order_id/{growwOrderId}/modify
    /v1/api/commodity_fo/commodity/v1/order/multi
    /v1/api/commodity_fo/commodity/v1/order/multi/cancel
    /v1/api/commodity_fo/commodity/v1/order/open_orders/contract_id/
    /v1/api/commodity_fo/commodity/v1/order/open_orders/contract_id/{contractId}
    /v1/api/commodity_fo/commodity/v1/order/order-history/search
    /v1/api/commodity_fo/commodity/v1/order/order-history/trades
    /v1/api/commodity_fo/commodity/v1/order/recent
    /v1/api/commodity_fo/commodity/v1/order/search
    /v1/api/commodity_fo/orders/open
    /v1/api/commodity_fo/smart-order/v1/gtt
    /v1/api/commodity_fo/smart-order/v1/gtt/
    /v1/api/commodity_fo/smart-order/v1/gtt/{growwOrderId}/cancel
    /v1/api/commodity_fo/smart-order/v1/gtt/{growwOrderId}/modify
    /v1/api/commodity_fo/smart-order/v1/gtt_order_id/
    /v1/api/commodity_fo/smart-order/v1/gtt_order_id/{growwOrderId}
    /v1/api/commodity_fo/smart-order/v1/gtt_orders
    /v1/api/core/equity/stocks/v2/order/search
    /v1/api/data/mf/web/v2/order_trend/
    /v1/api/equity/order-card/exchange/
    /v1/api/equity/order-card/exchange/{exchange}/contract-info
    /v1/api/etf_nfo/v2/order/create
    /v1/api/groww_mandate/v1/mandate/retry/
    /v1/api/groww_mandate/v1/mandate/retry/{mandateId}
    /v1/api/groww_mandate/v2/mandate_status/
    /v1/api/groww_mandate/v2/mandate_status/{mandateId}
    /v1/api/mandate/v1/detail/{mandateId}
    /v1/api/mandate/v1/get/all/mandates
    /v1/api/money/asba/mandate/v1/generate/intent/url
    /v1/api/nodal-payment/v1/init-payment-transaction
    /v1/api/nodal-payment/v1/status/payment/
    /v1/api/nodal-payment/v1/status/payment/{nodalTxnId}
    /v1/api/nodal-payment/v1/updateTransaction
    /v1/api/nodal-payment/v1/updateTransaction?transaction_id=
    /v1/api/order/purchase/v1/config
    /v1/api/order/v1/config/lumpsum
    /v1/api/order/v1/config/sip
    /v1/api/order/v1/folio_holdings/redemption_details
    /v1/api/order/v1/handling/preorder?schemes=
    /v1/api/order/v1/otp
    /v1/api/order/v1/otp/validate/
    /v1/api/order/v1/redeem/otp
    /v1/api/order/v1/redeem/otp/validate/
    /v1/api/order/v1/redemption/calculation
    /v1/api/order/v1/search/systematic_plan
    /v1/api/order/v1/search/systematic_plan/stats
    /v1/api/order/v1/stp/cancel?groww_order_id=
    /v1/api/order/v1/stp/status_check
    /v1/api/order/v1/switch/get_schemes_for_switch
    /v1/api/order/v1/switch/schemes
    /v1/api/order/v1/switch/switch_status
    /v1/api/order/v1/switch/track/
    /v1/api/order/v1/swp/cancel?groww_order_id=
    /v1/api/order/v1/swp/status_check
    /v1/api/order/v1/validate/lumpsum
    /v1/api/order/v1/validate/sip
    /v1/api/order/v2/folio_holdings/redeem
    /v1/api/order/v2/folio_holdings/redemption_details
    /v1/api/order/v2/poll/pending_redeem_order
    /v1/api/order/v2/redeem/otp
    /v1/api/order/v2/redeem/otp/validate/
    /v1/api/order/v2/search_orders
    /v1/api/order/v2/stp
    /v1/api/order/v2/switch/place_in_bse
    /v1/api/order/v2/swp
    /v1/api/order/v2/user/request
    /v1/api/order/v3/folio_holdings/redemption_details
    /v1/api/order/v3/search/pending_orders
    /v1/api/order/v4/search/request
    /v1/api/payments/v1/txn
    /v1/api/payments/v1/txn/withdraw
    /v1/api/payments/v2/txn/cancel_withdraw
    /v1/api/payments/v2/txn/failed
    /v1/api/payments_config/upe/v1/gupi/onboarding/mf
    /v1/api/payments_config/upe/v1/gupi/onboarding/stocks
    /v1/api/payments_config/upe/v1/instrument_list/mf
    /v1/api/payments_config/upe/v1/instrument_list/stocks
    /v1/api/payments_config/v2/instrument_list
    /v1/api/pg/funds/payin/bank-transfer/upe/v1/van-details
    /v1/api/pg/funds/payin/payments/upe/v1/init
    /v1/api/pg/funds/payin/payments/upe/v1/status_check?txnId=
    /v1/api/pg/upe/orchestrator/order/v1/execute
    /v1/api/pg/upe/orchestrator/order/v1/execute/mf
    /v1/api/pg/upe/orchestrator/order/v1/status
    /v1/api/pg/upe/orchestrator/order/v1/status/mf
    /v1/api/pg/upe/orchestrator/order/v1/status/mf?upeOrderId=
    /v1/api/pg/upe/orchestrator/order/v1/transaction/quick_checkout
    /v1/api/pg/upe/orchestrator/order/v1/update
    /v1/api/pg/upe/orchestrator/order/v1/update/mf
    /v1/api/pg/upe/orchestrator/payment/v1/validate_vpa
    /v1/api/pg/upe/orchestrator/payment/v1/validate_vpa/mf
    /v1/api/pg/upe/orchestrator/upi-autopay/v1/create-and-present
    /v1/api/pg/upe/orchestrator/v1/txn/reinit_otp
    /v1/api/pg/v1/
    /v1/api/pg/v1/check_status/txn/
    /v1/api/pg/v1/check_status/txn/{txnId}
    /v1/api/pg/v1/icici/direct_netbanking/transaction/
    /v1/api/pg/v1/icici/direct_netbanking/transaction/{txnId}
    /v1/api/pg/v1/icici/direct_netbanking/transaction/{txnId}/re-init-otp
    /v1/api/pg/v1/razorpay/
    /v1/api/pg/v1/razorpay/{txnId}/create_payment
    /v1/api/pg/v1/txn/
    /v1/api/pg/v1/txn/{growwTxnId}
    /v1/api/pg/v1/{txnId}/create_payment
    /v1/api/pg/v2/razorpay/
    /v1/api/pg/v2/razorpay/{txnId}/create_payment
    /v1/api/primaries/v1/bonds/ipo/order/active
    /v1/api/primaries/v1/bonds/ipo/order/historic
    /v1/api/primaries/v1/ipo/order/active
    /v1/api/primaries/v1/ipo/order/historic
    /v1/api/sip/v1/
    /v1/api/sip/v1/dates
    /v1/api/sip/v2/cancel_edit_sip_request/
    /v1/api/sip/v2/change_mandate?groww_sip_id=
    /v1/api/sip/v2/dates/edit_sip/
    /v1/api/sip/v2/edit_sip
    /v1/api/sip/v2/get_edit_request_tracking_details/
    /v1/api/sip/v2/step_up_sip
    /v1/api/sip/v2/step_up_sip/
    /v1/api/sip/v2/step_up_sip_config
    /v1/api/sip/v3/cancel_edit_sip_request/
    /v1/api/sip/v3/cancelled_sips
    /v1/api/sip/v3/create_mandate
    /v1/api/sip/v3/edit_sip
    /v1/api/sip/v3/get_sips
    /v1/api/sip/v3/groww_sip_id/
    /v1/api/sip/v4/details/
    /v1/api/sip/v4/edit_sip
    /v1/api/stocks/order-buffer/v1/order
    /v1/api/stocks/order-buffer/v1/order/
    /v1/api/stocks/order-buffer/v1/order/:growwOrderId/cancel
    /v1/api/stocks/order-buffer/v1/order/:growwOrderId/modify
    /v1/api/stocks/order-buffer/v1/order/multi/cancel
    /v1/api/stocks/smart-order/v1/cover-order
    /v1/api/stocks/smart-order/v1/cover-order/
    /v1/api/stocks/smart-order/v1/cover-order/{smartOrderId}/modify
    /v1/api/stocks/smart-order/v1/gtt
    /v1/api/stocks/smart-order/v1/gtt/
    /v1/api/stocks/smart-order/v1/gtt/{gttOrderId}/cancel
    /v1/api/stocks/smart-order/v1/gtt/{gttOrderId}/modify
    /v1/api/stocks/v1/advance-order/oco/orders?product=MIS
    /v1/api/stocks/v1/order/available_to_sell/symbol_isin/
    /v1/api/stocks/v1/order/available_to_sell/symbol_isin/{isin}
    /v1/api/stocks/v1/order/recent
    /v1/api/stocks/v1/order/trades
    /v1/api/stocks/v1/sip/mandate/create/
    /v1/api/stocks/v1/sip/mandate/create/{mandateId}
    /v1/api/stocks/v1/sip/orders/
    /v1/api/stocks/v1/sip/orders/count/
    /v1/api/stocks/v1/sip/orders/count/{sipId}
    /v1/api/stocks/v1/sip/orders/{sipId}
    /v1/api/stocks_fo/fno/order-orchestrator/single-order?orderSource=USER
    /v1/api/stocks_fo/fno/order-orchestrator/status/
    /v1/api/stocks_fo/fno/order-orchestrator/status/{requestId}
    /v1/api/stocks_fo/orders/open
    /v1/api/stocks_fo/smart-order/v1/gtt
    /v1/api/stocks_fo/smart-order/v1/gtt/
    /v1/api/stocks_fo/smart-order/v1/gtt/{gttOrderId}/cancel
    /v1/api/stocks_fo/smart-order/v1/gtt/{gttOrderId}/modify
    /v1/api/stocks_fo/stocks/v1/order/groww_order_id/
    /v1/api/stocks_fo/stocks/v1/order/groww_order_id/{growwOrderId}
    /v1/api/stocks_fo/stocks/v1/order/open_orders/contract_id/
    /v1/api/stocks_fo/stocks/v1/order/open_orders/contract_id/{contractId}
    /v1/api/stocks_fo/stocks/v1/order/search/all
    /v1/api/stocks_fo/stocks/v1/order/trades
    /v1/api/stocks_fo/stocks/v2/order/groww_order_id/
    /v1/api/stocks_fo/stocks/v2/order/groww_order_id/{growwOrderId}
    /v1/api/stocks_fo/stocks/v2/order/search
    /v1/api/stocks_fo/stocks/v3/order/search
    /v1/api/stocks_fo/stocks_router/v1/order/open
    /v1/api/stocks_fo/stocks_router/v1/order/recent
    /v1/api/stocks_fo/stocks_router/v1/smart-order/gtt_order_id/
    /v1/api/stocks_fo/stocks_router/v1/smart-order/gtt_order_id/{gttOrderId}
    /v1/api/stocks_fo/stocks_router/v1/smart_exit/order/user_trigger_id/
    /v1/api/stocks_fo/stocks_router/v1/smart_exit/order/user_trigger_id/{userTriggerId}
    /v1/api/stocks_fo/stocks_router/v2/smart-order/search/gtt/pending_orders
    /v1/api/stocks_fo/stocks_router/v2/smart-order/search/gtt_orders
    /v1/api/stocks_ipo/v1/order
    /v1/api/stocks_ipo/v1/order/
    /v1/api/stocks_ipo/v1/order/{growwOrderId}/cancel
    /v1/api/stocks_ipo/v3/orders/
    /v1/api/stocks_ipo/v3/orders/order_id/
    /v1/api/stocks_ipo/v3/orders/order_id/{growwOrderId}
    /v1/api/stocks_ipo/v3/orders/{searchId}
    /v1/api/stocks_pledge/v1/pledge/revoke
    /v1/api/stocks_portfolio/v2/holding/pledged
    /v1/api/stocks_router/v1/order/groww_order_id/
    /v1/api/stocks_router/v1/order/groww_order_id/{growwOrderId}
    /v1/api/stocks_router/v1/smart-order/gtt_order_id/
    /v1/api/stocks_router/v1/smart-order/gtt_order_id/{gttOrderId}
    /v1/api/stocks_router/v1/smart-order/search/gtt/pending_orders
    /v1/api/stocks_router/v5/dashboard/orders
    /v1/api/stocks_sgb/v1/order
    /v1/api/stocks_sgb/v1/order/cancel/
    /v1/api/stocks_sgb/v1/order/cancel/{growwOrderId}
    /v1/api/stocks_sgb/v1/order/groww_order_id/
    /v1/api/stocks_sgb/v1/order/groww_order_id/{growwOrderId}
    /v1/api/stocks_sgb/v1/order/listing/user
    /v1/api/stocks_sgb/v1/order/symbol/
    /v1/api/stocks_sgb/v1/order/symbol/{symbol}
    /v1/api/us/stocks/order
    /v1/api/us/stocks/order/
    /v1/api/us/stocks/order/card/assetId/
    /v1/api/us/stocks/order/card/user/
    /v1/api/us/stocks/order/closed/today
    /v1/api/us/stocks/orders
    /v1/api/us_stocks/v1/orders/
    /v1/api/us_stocks/v1/orders/preview
    /v1/api/us_stocks/v1/orders/search
    /v1/api/us_stocks/v1/orders/{orderId}
    /v1/api/us_stocks/v1/orders/{orderId}/cancel
    /v1/api/us_stocks/v1/orders/{orderId}/timeline
    /v1/api/us_stocks/v1/orders/{orderId}/trades
    /v1/api/us_stocks/v1/payment/doc/status
    /v1/api/us_stocks/v1/payment/doc/upload
    /v1/api/us_stocks/v1/payment/fund/axis/net_banking/cancel
    /v1/api/us_stocks/v1/payment/fund/axis/net_banking/init
    /v1/api/us_stocks/v1/payment/fund/axis/net_banking/status
    /v1/api/us_stocks/v1/payment/fund/cf/order
    /v1/api/us_stocks/v1/payment/fund/cf/order/cancel
    /v1/api/us_stocks/v1/payment/fund/cf/order/status
    /v1/api/us_stocks/v1/payment/fund/cf/pay
    /v1/api/us_stocks/v1/user/withdraw
    /v1/api/user/v1/mandate/
    /v1/api/user/v1/mandate/default/
    /v1/api/user/v1/mandate/default/{mandateId}
    /v1/api/user/v1/mandate/register?mandate_type=
    /v1/api/user/v1/mandate/{mandate_id}/status
    /v1/api/user/v2/freeze

## OTHER / unclassified  (173)

    /api/v1/aadhaarcardpages/
    /api/v1/aadhaarcardpages/{slug}
    /api/v1/action-hub/
    /api/v1/action-hub/{slug}
    /api/v1/aiki
    /api/v1/blogcategories
    /api/v1/blogs
    /api/v1/blogs/
    /api/v1/blogs/category/
    /api/v1/blogs/category/:slug
    /api/v1/blogs/{slug}
    /api/v1/calculators/
    /api/v1/calculators/{slug}
    /api/v1/creditcards/
    /api/v1/creditcards/{slug}
    /api/v1/custom-config/sebi-initiative-ticker
    /api/v1/dailydigests
    /api/v1/dailydigests/
    /api/v1/dailydigests/{slug}
    /api/v1/generalpages/
    /api/v1/generalpages/{slug}
    /api/v1/glossarypages/
    /api/v1/glossarypages/{slug}
    /api/v1/insurancepages/
    /api/v1/insurancepages/{parentPageSlug}/{slug}
    /api/v1/insurancepages/{slug}
    /api/v1/investor-relation/v2
    /api/v1/ipo-content
    /api/v1/ipo-product-content/
    /api/v1/ipo-product-content/{slug}
    /api/v1/ir-docs/
    /api/v1/ir-docs/announcement
    /api/v1/ir-docs/{category}
    /api/v1/loans/
    /api/v1/loans/{slug}
    /api/v1/pancardpages/
    /api/v1/pancardpages/{slug}
    /api/v1/press
    /api/v1/pricing
    /api/v1/regulatorypage
    /api/v1/route-seo-content
    /api/v1/rtopages/
    /api/v1/rtopages/{slug}
    /api/v1/rtopages/{stateSlug}/{citySlug}
    /api/v1/savingsaccounts/
    /api/v1/savingsaccounts/{slug}
    /api/v1/savingschemepages/
    /api/v1/savingschemepages/{slug}
    /api/v1/stocksinnews
    /api/v1/taxpages/
    /api/v1/taxpages/{slug}
    /api/v1/traders-corner
    /api/v1/updates/
    /api/v1/updates/{slug}
    /api/v1/weeklydigests
    /api/v1/weeklydigests/
    /api/v1/weeklydigests/{slug}
    /api/v2/ir-data/calculate
    /api/v2/ir-data/charts/area
    /api/v2/ir-data/charts/line
    /api/v2/updates
    /v1/api/aggregator/track/latest_track_state
    /v1/api/apex
    /v1/api/apex/oauth2/v1/consent/page/
    /v1/api/apex/oauth2/v1/consent/page/{clientId}
    /v1/api/apex/v1/token/s2s/vendor/cleartax/redirect
    /v1/api/asba-ledger/v1/account/transactions
    /v1/api/asba-ledger/v1/account/transactions/
    /v1/api/asba-ledger/v1/account/transactions/download
    /v1/api/asba-ledger/v1/account/transactions/{txnId}
    /v1/api/bff/invest_money/v1/is_deposit_blocked
    /v1/api/bff/invest_money/v1/is_withdraw_blocked
    /v1/api/bonds/screener/bonds-list
    /v1/api/commodity/oms/rms/basket-pqr/details
    /v1/api/commodity/v1/product/check_downtime
    /v1/api/commodity/v1/rate/graph/merchant/
    /v1/api/commodity/v1/rate/graph/merchant/{merchant}/type/{commodityType}/{buySell}
    /v1/api/commodity/v1/rate/merchant/
    /v1/api/commodity_fo/commodities/invest-advance-order/oco
    /v1/api/commodity_fo/commodities/invest-advance-order/oco/
    /v1/api/commodity_fo/commodities/invest-advance-order/oco/{ocoOrderId}
    /v1/api/commodity_fo/commodities/invest-advance-order/oco/{ocoOrderId}/cancel
    /v1/api/commodity_fo/commodity/market/market_timing
    /v1/api/commodity_fo/commodity/oms_rms/v1/exchange/
    /v1/api/commodity_fo/commodity/oms_rms/v1/exchange/{exchange}/contract/{contractId}/info
    /v1/api/commodity_fo/v1/invest-square-off/
    /v1/api/commodity_fo/v1/invest-square-off/contracts
    /v1/api/commodity_fo/v1/invest-square-off/{requestId}
    /v1/api/commodity_fo/v1/product/searchId/
    /v1/api/commodity_fo/v1/product/searchId/{searchId}
    /v1/api/commodity_fo/v1/product/symbol/
    /v1/api/commodity_fo/v1/product/symbol/{symbol}
    /v1/api/commodity_fo/v1/spot-price/all
    /v1/api/commodity_fo/v1/tr_live_prices/exchange/
    /v1/api/commodity_fo/v1/tr_live_prices/exchange/{exchange}/segment/COMMODITY/latest_prices_batch
    /v1/api/commodity_fo/v1/tr_live_prices/exchange/{exchange}/segment/COMMODITY/{token}/latest
    /v1/api/commodity_fo/v2/product/searchId/
    /v1/api/commodity_fo/v2/product/searchId/{searchId}
    /v1/api/dp/broker-service/v1/featureService/segmentFeature/readFeatureValues
    /v1/api/features/
    /v1/api/fno/oms/rms/basket-pqr/details
    /v1/api/fno/oms/rms/exchange/
    /v1/api/fno/oms/rms/exchange/{exchange}/contract/{contractId}/info
    /v1/api/fno/option-greeks/batch
    /v1/api/fno/v2/oms/rms/exchange/
    /v1/api/fno_user_blocking/v2/status
    /v1/api/fno_user_responsibility/v1/safe_pause/disable
    /v1/api/fno_user_responsibility/v1/safe_pause/enable
    /v1/api/gb/aggregator/v1/account/fetch
    /v1/api/gb/v1/tat/pre_withdrawal
    /v1/api/gb/v1/tat/status
    /v1/api/gb/v1/tat/status?transactionId=
    /v1/api/groww-news/v2/stocks/news/
    /v1/api/groww-news/v2/stocks/news/{gsin}
    /v1/api/groww_mandate/v2/
    /v1/api/groww_mandate/v2/upi_ap/create_mandate
    /v1/api/groww_mandate/v2/{mandateId}
    /v1/api/mf/v1/exchange/determine
    /v1/api/mf_cdsl/v1/edis/init
    /v1/api/mf_payments_config/v2/instruments/instrument_list
    /v1/api/physicalGold/v1/rates/component_order
    /v1/api/primaries/v1/bonds/ipo
    /v1/api/primaries/v1/bonds/ipo/open
    /v1/api/primaries/v1/bonds/ipo/summary
    /v1/api/primaries/v1/ipo/closed
    /v1/api/primaries/v1/ipo/open?v=2
    /v1/api/primaries/v1/ipo/upcoming
    /v1/api/stocks/v1/sip/
    /v1/api/stocks/v1/sip/{sipId}/cancel
    /v1/api/stocks/v1/sip/{sipId}/skip
    /v1/api/stocks_activation/v1/mtf/consent
    /v1/api/stocks_bo/opt_out_stock
    /v1/api/stocks_bo/opt_out_stock?referenceId=
    /v1/api/stocks_edis/v1/tpin/generate/custom_tpin
    /v1/api/stocks_fo/fno/invest-advance-order/oco
    /v1/api/stocks_fo/fno/invest-advance-order/oco/
    /v1/api/stocks_fo/fno/invest-advance-order/oco/primary-order
    /v1/api/stocks_fo/fno/invest-advance-order/oco/primary-order/
    /v1/api/stocks_fo/fno/invest-advance-order/oco/primary-order/{ocoOrderId}
    /v1/api/stocks_fo/fno/invest-advance-order/oco/{ocoOrderId}
    /v1/api/stocks_fo/fno/invest-advance-order/oco/{ocoOrderId}/cancel
    /v1/api/stocks_fo/fno/invest-advance-order/visibility/primary-order/oco-order-id/
    /v1/api/stocks_fo/fno/invest-advance-order/visibility/primary-order/oco-order-id/{ocoOrderId}
    /v1/api/stocks_fo/fno/v1/invest-square-off/
    /v1/api/stocks_fo/fno/v1/invest-square-off/contracts
    /v1/api/stocks_fo/fno/v1/invest-square-off/{requestId}
    /v1/api/stocks_ipo/v1/config
    /v1/api/stocks_ipo/v1/config/category_config
    /v1/api/stocks_ipo/v1/config/vpaList
    /v1/api/stocks_pledge/v1/pledgable/explore
    /v1/api/stocks_portfolio/v2/corporate_action/
    /v1/api/stocks_portfolio/v2/corporate_action/{type}/info
    /v1/api/stocks_rms/v1/physical_settlement/cancel_physical_settlement_request
    /v1/api/stocks_rms/v1/physical_settlement/check_if_already_requested_physical_settlement
    /v1/api/stocks_rms/v1/physical_settlement/create_physical_settlement_request
    /v1/api/stocks_rms/v1/physical_settlement/get_nearest_expiry_date
    /v1/api/stocks_router/v1/intraday_symbol_info/symbol_isin/
    /v1/api/stocks_router/v1/intraday_symbol_info/symbol_isin/{symbolIsin}
    /v1/api/us/stocks/data/assets/search-id/
    /v1/api/us/stocks/data/assets/search-id/{search_id}
    /v1/api/us/stocks/data/chart/symbol/
    /v1/api/us/stocks/data/live-data/details
    /v1/api/us/stocks/data/live-data/minimal
    /v1/api/us/stocks/data/market/calendar
    /v1/api/us_charting_service/v2/chart/exchange/US/segment/
    /v1/api/us_charting_service/v2/chart/exchange/US/segment/{segment}/{symbol}/{range}
    /v1/api/us_stocks/v1/beneficiary
    /v1/api/us_stocks/v1/cms/fetch/default_instructions
    /v1/api/us_stocks/v1/cms/fetch/steps
    /v1/api/us_stocks/v1/fx
    /v1/api/us_stocks/v1/market/status
    /v1/api/vpa_validation/v1/vpa/verify
    /v1/api/vpa_validation/v1/vpa/verify?vpa=

---

# The ones actually probed, with what came back

Every row below was called on 2026-08-27. `✅` means it returned usable data with
no authentication. Sizes are real response sizes.

## Mutual funds

| Endpoint | Status | What it gives |
|---|---|---|
| `GET /v1/api/search/v3/query/filter_derived_data/st_filter?page=0&size=4000` | ✅ 5.3 MB | The universe. 3,410 rows, all Direct + available. Filter `scheme_type=="Growth"` → **1,741 rows / 1,686 unique AMFI codes**. Carries expense_ratio, aum, fund_manager, min_sip, min_lumpsum, exit_load, sub_category, risk, groww_rating. |
| `GET /v1/api/data/mf/web/v5/scheme/search/{search_id}` | ✅ 191 KB | **The best single endpoint on Groww.** See below. |
| `GET /v1/api/data/mf/web/v6/scheme/search/{search_id}` | ✅ 191 KB | Byte-identical to v5 when probed. |
| `GET /v1/api/data/mf/web/v2/scheme/search/{search_id}` | ✅ 189 KB | v5 minus 10 fields. |
| `GET /v1/api/data/mf/web/v1/scheme/search/{search_id}` | ✅ 37 KB | Legacy. Holdings are **positional arrays** — avoid. |
| `GET /v1/api/data/mf/web/v4/scheme/meta_data?search_id=` | ✅ 14 KB | `{response, data}` |
| `GET /v1/api/data/mf/v1/nfo/list` | ✅ 12 KB | `{closed, live}` — new fund offers |
| `GET /v1/api/search/v3/query/mf_prime_screener/st_prime` | ✅ but empty | Prime-only screener; returns 0 rows unauthenticated |
| `GET /v1/api/data/mf/web/v1/similar/scheme/top` · `/fetch/fund_news/` · `/v2/order_trend/` | 200, empty | Exist, return nothing for the params tried |
| `/v1/api/data/mf/web/v1/scheme/portfolio/{slug}` · `/groww_popular_funds` | 502 | Path exists, upstream errors |

### What v5 carries that nothing else free does

    isin, benchmark_name, registrar_agent, rta_scheme_code, launch_date,
    allotment_date, stamp_duty, portfolio_turnover, lock_in

    holdings              152 rows for PPFAS, NAMED OBJECTS (not positional):
                          company_name, nature_name (EQUITY/DEBT/CASH/REALEST/MF),
                          sector_name, instrument_name, rating, market_value,
                          corpus_per (weight %), portfolio_date,
                          stock_search_id  ← joins a holding to its company page

    fund_manager_details  name, date_from (tenure start), education, experience

    historic_fund_expense 1,166 rows for PPFAS, 2013-10 → 2026-08, daily+monthly,
                          with turn_over_ratio on 172 of them.
                          → TER is a TIME SERIES, not a number.

    historic_exit_loads   dated, with the note text as it changed over time

    stats                 FUND_RETURN / CATEGORY_AVG_RETURN / RANK_WITHIN_CATEGORY
                          at 1y/3y/5y — ready-made peer comparison

    return_stats          sharpe_ratio, beta, standard_deviation, mean_return
                          ← Groww's own UI never shows any of these

    analysis              PROS/CONS array, e.g.
                          PROS "Lower expense ratio: 0.69%"
                          PROS "Higher alpha: 4.17 ... vs NIFTY 500 TRI in the last 3Y"
                          CONS "Consistently lower annualised returns than category
                                average for the past 1Y, 3Y and 5Y"
                          ← computed server-side, fetched by the page, NEVER RENDERED

## Stocks

| Endpoint | Status | What it gives |
|---|---|---|
| `GET /v1/api/stocks_data/v1/company/search_id/{slug}` | ✅ 12 KB | header(isin, industry) · fundamentals · shareHoldingPattern · priceData · financialStatement · **financialStatementV2 (CONSOLIDATED *and* STANDALONE, 5y yearly + 5q quarterly)** · similarAssets · **fundsInvested** (which funds hold this stock, with investedAumPercent) |
| `GET .../company/search_id/{slug}/financial_statements` | ✅ 16 KB | `financialSummary, header, statements` |
| `GET /v1/api/stocks_data/v1/accord_points/exchange/NSE/segment/CASH/latest_prices_ohlc/{SYM}` | ✅ 608 B | **Live LTP**, dayChange, high/low, circuit bands, cumulative buy/sell qty. Replaces NSE `quote-equity`, which is 403. |
| `GET /v1/api/stocks_data/v1/tr_live_prices/.../{SYM}/latest` | ✅ | Same shape |
| `GET /v1/api/stocks_data/v1/tr_live_book/.../{SYM}/latest` | ✅ 493 B | `buyBook / sellBook` — live order book depth |
| `GET /v1/api/stocks_data/v1/accord_company/isin/{ISIN}/minimal` | ✅ 772 B | **ISIN → searchId + BSE/NSE codes.** The join key mapper. |
| `POST /v1/api/stocks_data/v1/all_stocks` | ⚠️ 200 | Screener. Body shape comes from `filtersV2`. **Returned only 32 records unfiltered — not a usable full universe.** |
| `GET /v1/api/stocks_data/v1/all_stocks/filtersV2` | ✅ 7.5 KB | `defaultReqDto` (the request body) + full INDUSTRY/INDEX filter taxonomy |
| `GET /v1/api/stocks_data/v1/etfs` | ✅ 9.5 KB | `{etfs, total}` |
| `GET /v1/api/equity/data/v1/shareholding-patterns/holders/{growwContractId}` | ✅ 18.7 KB | Named shareholders |
| `GET /v1/api/stocks_data/v1/market/market_timing` | ✅ 933 B | Trading calendar |
| `GET /v1/api/stocks_fo_data/v1/derivatives/{slug}/contract` | ✅ 3.2 KB | F&O chain + market depth |
| `GET /v1/api/search/v3/query/global/st_p_query?query=&page=&size=&web=true` | ✅ | Search → isin, search_id, nse_scrip_code, exchange, entity_type |

## 🔴 Charting is NOT a research source

    /v1/api/charting_service/v2/chart/exchange/NSE/segment/CASH/{SYM}/{range}

    range=all  → only 81 candles spanning 2002-07-19 → 2026-08-03
    range=5y   → 111 candles
    range=1y   →  80 candles

**Downsampled for drawing.** It cannot back a backtest. Daily history still has to
come from the NSE bhavcopy archive or yfinance.

---

# Three data-quality traps, each measured not assumed

**1. TER has a bad tail in both sources.** Against SEBI reg 52(6) ceilings
(equity 2.25%, index/ETF 1.00%, and a direct plan must sit below its own regular
plan): Groww 31 of 1,677 above ceiling, AMFI 12 of 1,408 above. Groww shows 13
*index* funds above the 1.00% index cap, worst **8.66%**. But on the 1,233 funds
in both sources they agree within 0.10pp **94.2%** of the time.
→ Carry both, require agreement, and refuse to rank on cost where they disagree.

**2. `category_info.sub_type` on the detail endpoint is garbage.** Sampled 60
funds: **0 agreed** with the universe endpoint's `sub_category`, 51 disagreed.
It labels essentially every equity fund `Contra` and every debt fund `Gilt`.
Using it would collapse 1,686 funds into two peer groups and the ranking would
look completely normal on screen.
→ Category comes from the universe endpoint only.

**3. `groww_rating` is unexplained and self-contradicting.** The page shows a bare
digit with no scale. Groww's own `<meta description>` calls it "2/10" while its
JSON-LD says `bestRating: 5`, on the same page. PPFAS carries `groww_rating: 5`
while Groww's own `analysis` array lists a CONS of "consistently lower annualised
returns than category average for 1Y, 3Y and 5Y".
→ Never surface it as a rating. Store it, ignore it.

Also: `sip_return3y` and `sipReturn3y` both exist on the universe row with
different values (43.44 vs 27.43 on SBI Gold). The v5 endpoint resolves this —
`simple_return` is cumulative point-to-point (3y = 49.99%) and `sip_return` is
SIP/XIRR-style (3y = 6.34%). Neither universe-row field is read.
