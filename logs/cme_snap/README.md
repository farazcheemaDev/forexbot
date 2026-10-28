# CME settlement snapshots (recorded by hand from the browser pane; CME's free feed keeps only 5 trade dates)

Source: `https://www.cmegroup.com/CmeWS/mvc/Settlements/Futures/Settlements/<productId>/FUT?strategy=DEFAULT&tradeDate=MM/DD/YYYY&pageSize=500`
(product ids: gold 437, copper 438, palladium 445, platinum 446, silver 458), read from a script running INSIDE the cmegroup.com page in the browser
pane. The same URL from a plain script returns 403 (CME's bot protection; not bypassed). `/CmeWS/mvc/Settlements/Futures/TradeDate/<id>` lists the
available dates: always 5. Anything older is empty - history is CME DataMine (paid).

- `2026-10-27.csv`  the final settlement, volume and open interest by contract month on 2026-10-27 (gold / silver / copper: months under ~1,000
  open interest left out; palladium and platinum complete).
- `pa_pl_oi_5d.json`  palladium and platinum open interest by contract month and the totals of all five products for 2026-10-21 .. 10-27: the start
  of the roll out of the delivery month (platinum's JAN -> APR has begun; palladium's DEC -> MAR has barely started).

What these are for: `positioning_lean.py` reads the latest file to show how much of each metal's open interest still sits in the next delivery
month and how many days remain to first notice. The record has to be kept going forward (one file a day or a week); it cannot be rebuilt.
