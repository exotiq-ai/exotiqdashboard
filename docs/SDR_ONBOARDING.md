# SDR Onboarding -- "How This Works"

This document lives as a new tab in the dashboard. It's a step-by-step guide for a new SDR on how to use the Exotiq Intelligence Pipeline.

---

## The Stack (What We Built)

**One system, two layers:**

**1. The Intelligence Dashboard (where you work):**
This React app is your command center. It shows you every lead, their score, their enrichment data, their contact info, and their outreach status. You'll spend most of your day here managing the approval queue and reviewing leads.

**2. GoHighLevel (where the team executes):**
Once a lead is approved and pushed, it lives in GHL. The LEx team manages all conversations, appointments, and pipeline stages there. You won't touch GHL directly, but it's where your approved leads end up.

---

## The Goal

Your job is to get qualified exotic car rental operators on a 15-minute demo call with Gregory.

You'll do this by managing the outreach queue, personalizing drafts, and escalating warm responses.

---

## Lead Lifecycle (Three Stages)

Every lead in the system moves through three stages. Understanding this is critical.

### Stage 1: Prospect (DM-Only)
- We only have the company name and an IG handle. No email or phone.
- These leads live only in our dashboard. They are NOT in GHL yet.
- You can approve and send DMs to Prospects freely.
- When you click "Approve DM" for a Prospect, it simply marks the copy as ready for manual sending. No GHL push happens.

### Stage 2: Qualified Lead (GHL-Ready)
- A Prospect who has responded and given us their email or phone number.
- Once you have contact info, click the "Promote to GHL" button on their card.
- This creates the contact in GoHighLevel and officially moves them into the sales pipeline.
- From this point, they appear in both the dashboard AND GHL.

### Stage 3: GHL Opportunity (Execution)
- The lead is now a full contact and opportunity in GoHighLevel.
- The closing team (or Gregory) manages all further communication in GHL.
- Our dashboard syncs their pipeline stage, but execution happens in GHL.

**Key Rule:** A lead MUST have an email or phone number before it can be promoted to GHL. DMs can go out to anyone with an IG handle.

---

## Your Daily Workflow (Step-by-Step)

This is your daily playbook. Run it every morning.

### Step 1: Review the Morning Brief (9:00 AM)

- Check the `#exotiq-outreach-ops` Slack channel for Saul's automated morning briefing.
- It will tell you:
  - New leads that were discovered overnight
  - Warm responses that came in
  - Follow-ups that are due today
  - Stale leads that need attention

### Step 2: Clear the Approval Queue (9:15 AM)

- Go to the **Approval Queue** tab in the dashboard.
- This is your primary workspace. It's a list of all outbound messages (IG DMs, emails, SMS) that Saul has drafted.
- For each draft, you will see one of two approve buttons:

  - **"Approve DM"** (for Prospects without email/phone): This approves the DM copy for manual sending. It does NOT push to GHL. Copy the message, go to Instagram or Facebook, and send it manually. Then mark it as "Sent" in the dashboard.
  - **"Approve & Push to GHL"** (for leads with email/phone): This approves the message AND creates the contact in GoHighLevel.

- Other options remain the same:
  - **Edit:** Tweak the draft, then Approve.
  - **Hold:** Park it for later.
  - **Reject:** Kill this touch.

- **Your goal:** Get the queue to zero every day.

### Step 2.5: Promote Warm Prospects (Ongoing)

- When a Prospect responds to a DM and shares their email or phone number:
  1. Go to the lead's card in the **All Leads** tab.
  2. Click the **"Promote to GHL"** button.
  3. Enter their email and/or phone number.
  4. Click **Confirm**. The system will create their contact in GHL and move them to Stage 2 (Qualified Lead).

- This is a critical step. It's how leads graduate from "DM conversations" to "real sales pipeline."

### Step 3: Enroll New Leads into Sequences (10:00 AM)

- Go to the **All Leads** tab.
- Filter for leads with `Status = New` and `Score >= 3`.
- For each new lead:
  1. Expand the lead card, review the enrichment intel.
  2. Scroll down to the **Sequences** panel.
  3. Click "Enroll in Sequence" and choose the best one:
     - **"New Operator 14-Day"** for Score 3-4 leads.
     - **"Score 5 Personal"** for Score 5 leads (this queues a call for Gregory).
     - **Event-specific sequences** (like "F1 Miami") for leads in that market.
- Once enrolled, Saul will automatically draft the first touch and it will land in your Approval Queue.

### Step 4: Handle Warm Responses (as they come in)

- When a lead replies, Saul will classify the response and escalate it to you in Slack.
- Go to the lead's card in the dashboard.
- Review the conversation history.
- Your job is to **book the demo.**
- Use the provided Calendly link: `https://calendly.com/hello-exotiq`
- Once booked, move the lead to the "Demo Scheduled" stage in GHL (or flag for Saul to do it).

### Step 5: Manual Outreach (IG and Facebook DMs)

- Some touches in the Approval Queue will be for IG or FB Messenger.
- Since Saul can't send these automatically, your workflow is:
  1. Click Approve on the draft in the queue.
  2. The dashboard will show you the approved copy.
  3. Copy the message.
  4. Go to Instagram or Facebook and send it manually.
  5. Mark the touch as "Sent" in the dashboard.

- This is critical. If you don't mark it as sent, the sequence will stall.

---

## What Not to Do

- **Don't go rogue.** Stick to the approved templates and sequences. The messaging is tested.
- **Don't try to push a Prospect to GHL without contact info.** Use the "Promote" button only when you have their email or phone.
- **Don't forget to mark manual DMs as sent.** This is the #1 failure point.
- **Don't engage in long back-and-forth conversations.** Your job is to book the demo. After 2-3 messages, push for the call.
- **Don't skip the Promote step.** When a Prospect gives you their contact info, promote them immediately. If they stay as a Prospect, the closing team can't see them in GHL.

---

## How Saul Helps You

- **He researches.** You get leads with phone numbers, emails, fleet sizes, and IG handles already filled in.
- **He scores.** You know who to prioritize (Score 5s go to Gregory, Score 3-4s are your bread and butter).
- **He drafts.** You're not writing cold outreach from scratch. You're a reviewer and editor.
- **He orchestrates.** He queues up the right touch on the right day for every lead.
- **He classifies.** He reads replies and tells you who's warm so you can jump on it.

Your job is the human touch: personalizing the last 10% of a draft, making the final decision to send, and booking the demo when a lead raises their hand.

---
## Open Questions for the SDR

- How much personalization do you want to do per message? 1 minute, 5 minutes?
- What's your comfort level with different channels (email, SMS, IG, FB)?
- How do you want to be notified of warm replies (Slack, email, SMS)?

This doc plus 30 minutes with Gregory and the dashboard is the full onboarding.
