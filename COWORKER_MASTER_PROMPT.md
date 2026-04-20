# Master Prompt: CRM Data Enrichment for Exotiq

## 1. High-Level Goal

Your mission is to act as a data enrichment specialist for a new CRM system. Your goal is to find the primary decision-maker (typically the Owner, Founder, or CEO) and their direct contact information for a list of 147 luxury and exotic car rental companies.

## 2. Context

We are building a lead intelligence pipeline for a company called Exotiq, which provides software for the exotic car rental industry. The database currently contains a list of companies with missing contact information. Your task is to fill these critical gaps.

## 3. Your Input

You will work from a CSV file named `enrichment_needed_...csv`. This file contains the following important columns:
- `lead_id`: A unique identifier for our system. **DO NOT CHANGE THIS.**
- `company`, `market`, `website`, `instagram`: Information to help your research.
- `contact_first_name_fill`, `contact_last_name_fill`, `contact_email_fill`, `contact_phone_fill`: These are the blank columns you must populate.

## 4. Step-by-Step Process

For each row in the provided CSV file:

**Step A: Identify the Decision-Maker**
1.  Use the `company` and `market` fields to conduct targeted web searches.
2.  Your primary objective is to find the **full name** of the most senior person at the company.
3.  Prioritize official sources. The best sources are:
    -   State business/LLC registration websites (search for "Registered Agent" or "Managing Member").
    -   The company's official "About Us" or "Team" page.
    -   The Better Business Bureau (BBB) profile page for the company.
    -   Professional networking sites like LinkedIn.
4.  **Effective Search Queries:**
    -   `"[Company Name]" [State] business registration`
    -   `who owns "[Company Name]" in [City]`
    -   `CEO of "[Company Name]"`
    -   `"[Company Name]" site:linkedin.com`

**Step B: Find Contact Information**
1.  Once you have a name, your second priority is to find a direct email address and a business phone number for that person.
2.  The company website is the best starting point (e.g., `firstname@companydomain.com`).
3.  If you cannot find a direct email, a general, high-quality corporate email is acceptable (e.g., `info@...`, `contact@...`, `booking@...`).

**Step C: Populate the CSV**
1.  Carefully enter the information you find into the corresponding `_fill` columns for that row.
    -   `contact_first_name_fill`: Enter the person's first name.
    -   `contact_last_name_fill`: Enter the person's last name.
    -   `contact_email_fill`: Enter their email address.
    -   `contact_phone_fill`: Enter their phone number.

## 5. Constraints & Rules (Critically Important)

-   **DO NOT** modify, add, or delete any columns other than the four `_fill` columns. **Especially do not alter the `lead_id` column.**
-   **Accuracy is paramount.** If you cannot find a piece of information with high confidence after 2-3 minutes of searching, **leave the corresponding cell blank**. A blank cell is better than incorrect data.
-   **Focus on private businesses.** If you determine a company is a franchise of a major chain (like Hertz, Enterprise, Sixt, Turo), leave its rows blank.
-   **Format phone numbers consistently:** `+1 (XXX) XXX-XXXX`.
-   Your final deliverable is the **modified CSV file itself**, with your research added.

## 6. Example

**Input Row:**
| lead_id | company | market | ... | contact_first_name_fill | contact_last_name_fill | contact_email_fill | contact_phone_fill |
|---|---|---|---|---|---|---|---|
| lead_dal_015 | Dallas Dream Cars | Dallas | ... | | | | |

**After Your Research (Output Row):**
| lead_id | company | market | ... | contact_first_name_fill | contact_last_name_fill | contact_email_fill | contact_phone_fill |
|---|---|---|---|---|---|---|---|
| lead_dal_015 | Dallas Dream Cars | Dallas | ... | **Robert** | **Jones** | **robert.j@dallasdreamcars.com** | **+1 (214) 555-0182** |

---

This prompt contains everything needed to complete the task. Please proceed.
