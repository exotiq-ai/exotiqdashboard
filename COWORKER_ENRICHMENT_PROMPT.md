# Manual Enrichment Task: Find Key Decision-Makers

## Goal
To find the full name of the primary owner or key decision-maker for a list of 5 exotic car rental companies.

## Task
For each company in the input list below, perform targeted web searches to identify a person of authority. Your primary sources should be:
1.  **State Business/LLC Registrations:** Search for the official business registration in the company's state. Look for terms like "Registered Agent," "Owner," "Managing Member," or "Principal."
2.  **Better Business Bureau (BBB):** Search the BBB for the company profile. The "Business Details" section often lists principal contacts.

**Example Search Queries:**
- `"[Company Name] LLC" [State] business registration`
- `"[Company Name]" Better Business Bureau owner`
- `who owns "[Company Name]" in [City]`

---

## Input List

1.  **Company:** "Prestige Luxury Rentals", **Market:** "Miami, FL"
2.  **Company:** "Royalty Exotic Cars", **Market:** "Las Vegas, NV"
3.  **Company:** "Cloud 9 Exotics", **Market:** "New York, NY"
4.  **Company:** "Diamond Exotic Rentals", **Market:** "Miami, FL"
5.  **Company:** "Carefree Lifestyle", **Market:** "Miami, FL"

---

## Required Output Format
Provide the output as a simple list, with the person's full name. If you cannot confidently identify a single key person after 2-3 minutes of searching, return "NOT FOUND".

**Example:**
```
Prestige Luxury Rentals: John Smith
Royalty Exotic Cars: Jane Doe
Cloud 9 Exotics: NOT FOUND
...
```

---

## Constraints
- **Focus ONLY on the person's full name.**
- **DO NOT** search for email addresses, phone numbers, or social media profiles. I will handle that part.
- If you find multiple names, provide the one that seems most senior (e.g., Owner > General Manager).
- Stick to official sources (state registrations, BBB) where possible.
