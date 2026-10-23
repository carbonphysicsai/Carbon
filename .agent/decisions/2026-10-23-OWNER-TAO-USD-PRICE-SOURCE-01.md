# OWNER-TAO-USD-PRICE-SOURCE-01: the joining cost shows an approximate USD value from CoinGecko's public price

Date: 2026-10-23
Status: APPROVED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae). Offered "(a) CoinGecko's free public price, shown as 'about $X'" or "(b) TAO only", the owner replied: "a".
Resolves: owner decision #9 (HANDOFF_PLAN, U-c).

## Decided

- Launchpad shows the joining cost (and any other TAO amount shown to the miner for funding) in TAO, plus "about $X" taken from CoinGecko's free public TAO/USD price.
- The TAO amount is authoritative. The USD figure is display only and labelled approximate, with its time. If the price can't be fetched, show TAO only, never a stale or invented number.
- The price fetch sends no wallet address, hotkey or other miner data, only the public price query.
- This is display only. Price never enters scoring, eligibility or any economic mechanism.
