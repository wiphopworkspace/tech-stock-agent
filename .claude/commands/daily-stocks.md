---
description: Summarize tech/chip/AI stock news in Thai and email it
---

You are generating the daily Thai-language tech/semiconductor/AI stock briefing.
Do everything yourself — do NOT call any external LLM API. You are the summarizer.

## Steps

1. **Fetch the data.** Run `python fetch_data.py` and read its JSON output from stdout.
   The JSON has `date`, `flagged_tickers`, and a `results` array. Each result has
   `ticker`, `group` (chips / ai_bigtech), `pct_change_1d`, `pct_change_5d`,
   `volume_ratio`, `flagged`, and `news` (headlines for flagged tickers).

2. **Build a STRUCTURED Thai summary** — not a wall of text. You will write a JSON
   object with exactly this shape (all human-readable text in Thai):

   ```json
   {
     "date": "YYYY-MM-DD",
     "title": "สรุปหุ้นเทค/ชิป/AI ประจำวัน",
     "tldr": "หนึ่งบรรทัด: สิ่งสำคัญที่สุดที่เกิดขึ้นวันนี้",
     "gainers": [
       {
         "ticker": "MU",
         "price": 1068.58,
         "pct_change": 8.86,
         "summary": "สองประโยคภาษาไทย: อะไรขยับและทำไม อ้างอิงหัวข้อข่าว",
         "sentiment": "positive"
       }
     ],
     "losers": [
       {
         "ticker": "PLTR",
         "price": 129.84,
         "pct_change": -3.61,
         "summary": "สองประโยคภาษาไทย: อะไรขยับและทำไม",
         "sentiment": "negative"
       }
     ],
     "sector_overview": [
       "ธีมที่ 1 ที่เชื่อมโยงหลายหุ้น",
       "ธีมที่ 2 ..."
     ]
   }
   ```

   Rules for the fields:
   - **tldr**: ONE line — the single most important thing that happened today.
   - **gainers / losers**: take only the `flagged` tickers. Put `pct_change_1d > 0`
     in `gainers`, `pct_change_1d < 0` in `losers`. Sort each group by the size of
     the move (largest magnitude first).
   - **price**: use `last_close`. **pct_change**: use `pct_change_1d`.
   - **summary**: exactly 2 Thai sentences — (1) what moved (ราคา % และวอลุ่มผิดปกติไหม)
     and (2) why, based on the news headlines. Do NOT invent numbers; use the JSON.
   - **sentiment**: one of `"positive"`, `"negative"`, `"neutral"` (the email renders
     these as ข่าวเชิงบวก / ข่าวเชิงลบ / ข่าวเป็นกลาง).
   - **sector_overview**: 3–5 short Thai bullet strings with cross-cutting themes
     (ทิศทางกลุ่มชิป, กระแส AI, หุ้นใหญ่, ปัจจัยมหภาค).

3. **Tone:** neutral and factual. NO buy/sell/hold calls, no price targets.

4. **Empty case:** if `flagged_tickers` is empty, set `gainers` and `losers` to `[]`,
   write a `tldr` saying no stocks crossed today's thresholds, and still fill
   `sector_overview` with a brief read of the watchlist from `results`.

5. **Write the file.** Save the JSON to `summaries/YYYY-MM-DD.json` (use the `date`
   from fetch_data). Create the `summaries/` folder if it does not exist. Write valid
   UTF-8 JSON (Thai characters as-is, not escaped).

6. **Email it.** Run `python send_email.py summaries/YYYY-MM-DD.json` with the matching
   path. The script renders the JSON into scannable HTML cards.

7. **Print the summary** in the terminal as well (a readable Thai version) so the user
   sees it immediately.

## Notes
- All amounts/percentages come from fetch_data's JSON — do not invent numbers.
- The JSON summary file is the single source of truth that gets emailed, so make it
  complete and valid before sending.
