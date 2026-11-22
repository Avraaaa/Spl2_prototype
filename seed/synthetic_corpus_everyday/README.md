# Everyday request corpus spec (DataSoft bank support portal)
Context: Bangladeshi banks file requests to their software vendor DataSoft about its core-banking / internet-banking products. The writer is a bank's Issue Officer (branch or head-office IT/operations staff) on an ordinary working day. Requirements say a request has: title, description, request type (bug / change / feature / support), affected product/module, priority, attachments; BUG requests also carry environment, steps to reproduce, expected result and actual result.

Write ONE JSON file (UTF-8, valid JSON only) with this shape (same as the existing corpus, plus bug evidence fields):
{
  "area": "<area id>",
  "groups": [
    {
      "group_id": "<area>-e01",
      "label": "Authentication|Transaction|Performance|Database|User Interface",
      "product": "Internet Banking|Mobile App|Core Banking|Card Management|ATM Switch|Reports",
      "module": "<short module>",
      "error_code": "<code or null>",
      "request_type": "bug|change|feature|support",
      "requests": [
        {"variant": "English|Bangla|Banglish|Code-switched|Typo", "request_type": "<same as group>", "priority": "low|medium|high|critical",
         "title": "...", "description": "...",
         "environment": "<bug only, e.g. 'Live, branch PC Windows 10, Chrome' / 'UAT' / 'Android app v3.2'>",
         "steps_to_reproduce": "<bug only, numbered or casual steps>",
         "expected_result": "<bug only>", "actual_result": "<bug only>",
         "attachments_mentioned": ["screenshot.png", "error_log.txt"]   // optional, names only
        }
        // exactly 5 requests per group, one per variant: English, Bangla, Banglish, Code-switched, Typo
      ]
    }
  ],
  "hard_negatives": [ { "neg_id": "<area>-en01", "near_group": "<group_id>", "label": "...", "product": "...", "module": "...", "error_code": "...", "variant": "...", "request_type": "...", "priority": "...", "title": "...", "description": "...", plus the bug-only fields when request_type is bug } ],
  "sensitive_cases": []
}
Omit the four bug-only fields (do not include them) when request_type is not bug.

Type mix per file (by group): about 40% bug, 20% change, 15% feature, 25% support.
- bug: something broke ("transfer debited but beneficiary not credited").
- change: modify existing behaviour ("increase daily NPSB limit field to 7 digits", "change SMS wording", "add branch code column to the report").
- feature: something new ("need bulk salary upload", "want QR login option", "dashboard for pending cheques").
- support: how-to / clarification / access / data request ("how do we reverse a wrongly posted voucher?", "please reset teller user", "need last month audit export", "training for new release").

Make it read like REAL day-to-day users, not polished specs:
- Mixed quality: some short and vague ("login problem since morning, pls check urgent"), some detailed; polite openings ("Dear Sir", "Kindly", "আসসালামু আলাইকুম"), urgency ("customer is waiting at the counter"), references to branches, customers, yesterday's EOD, month-end, a screenshot "attached".
- Bug evidence written the way officers actually write it: environment sometimes partial ("live server, branch 0123 PC"), steps sometimes 2-3 casual lines, expected/actual short. Write the evidence fields in the same language variant as the request.
- The 5 requests in a group describe the SAME underlying need/incident with genuinely different wording, detail, length and tone. NOT translations of each other; no shared title pattern; no "case 001", no "Synthetic".
- Bangla in Bangla script (technical words like OTP, NPSB, BEFTN, EOD, login may stay English); Banglish romanized with inconsistent spelling; Code-switched natural mix; Typo = English with 2-4 realistic typos.
- Hard negatives: same product/module (often same keywords or error code) but a different need/problem; they may be a different request type.
- Fake data only: no real names, real bank names, real phone/card/account numbers. Generic roles only.
- Validate the JSON parses before finishing.
