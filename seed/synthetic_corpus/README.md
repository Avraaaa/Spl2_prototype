# Synthetic corpus spec (DataSoft bank support portal)
Context: Bangladeshi banks file support requests to a software vendor (DataSoft) about its core-banking / internet-banking products. Requests are written by bank officers in English, Bangla, Banglish (romanized Bangla), code-switched (Bangla+English mixed in one sentence), or English with realistic typos.

Write ONE JSON file (UTF-8, valid JSON, no comments, no trailing text) with this exact shape:
{
  "area": "<area id>",
  "groups": [
    {
      "group_id": "<area>-g01",
      "label": "Authentication|Transaction|Performance|Database|User Interface",
      "product": "Internet Banking|Mobile App|Core Banking|Card Management|ATM Switch|Reports",
      "module": "<short module name, e.g. Login, Fund Transfer, NPSB, BEFTN, RTGS, Card PIN, Statement, Teller>",
      "error_code": "<e.g. E-1102 or null>",
      "requests": [
        {"variant": "English", "request_type": "bug|change|feature|support", "priority": "low|medium|high|critical",
         "title": "...", "description": "..."}
        // one request per variant: English, Bangla, Banglish, Code-switched, Typo  (exactly 5)
      ]
    }
  ],
  "hard_negatives": [
    {"neg_id": "<area>-n01", "near_group": "<group_id it resembles>", "label": "...", "product": "...", "module": "...",
     "error_code": "<often the SAME code as near_group>", "variant": "English|Bangla|Banglish|Code-switched|Typo",
     "request_type": "...", "priority": "...", "title": "...", "description": "..."}
  ],
  "sensitive_cases": [
    {"variant": "...", "text": "<a realistic request sentence or two containing sensitive values>",
     "expected": [{"value": "<exact substring>", "type": "OTP|CARD|ACCOUNT|NID|EMAIL|PHONE"}],
     "must_not_mask": ["<exact substrings that must stay visible: error codes, versions, dates, amounts, SR-1043 refs, labelled Txn ID / Order no references>"]}
  ]
}

Quality rules (this is the whole point):
- The 5 requests in a group describe the SAME underlying incident but must be genuinely different: different wording, different detail emphasis, different length (1-5 sentences), different reporter tone. NOT translations of one template. Titles must not share a fixed pattern; no "case 0001", no "Synthetic" prefix.
- Bangla must be natural Bangla script (technical terms like OTP, NPSB, BEFTN, login may stay in English as officers write them). Banglish = romanized Bangla, inconsistent spelling is fine (ashche/ashe, hocche/hoche, parchi/partesi). Code-switched = natural mix. Typo = English with 2-4 realistic typos.
- Hard negatives share product/module and often the same error code or keywords as a group, but describe a DIFFERENT problem (different root cause/symptom). They must not be duplicates.
- Sensitive values are fake: OTP 4-8 digits near the word OTP/PIN/code (also Bangla digits ০-৯ sometimes, also Bangla words like ওটিপি), card numbers 16 digits from test ranges (4111 1111 1111 1111 style, spaced/dashed/plain), account numbers 10-17 digits near "account/a/c/হিসাব", NID 10/13/17 digits near NID/জাতীয় পরিচয়পত্র/এনআইডি (sometimes in Bangla digits), emails at example.test / example.com, BD mobile numbers 01[3-9]XXXXXXXX or +8801... Include must_not_mask lookalikes (E-4012, v2.4.1, 12/11/2026, BDT 50,000, SR-1043, "Txn ID 7788990011" ).
- No real person names, real bank names, or real numbers. Use generic roles ("customer", "branch officer").
- Validate your JSON parses before finishing (e.g. node -e "JSON.parse(require('fs').readFileSync(process.argv[1],'utf8'))" <file>).
