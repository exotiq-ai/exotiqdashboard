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
- For each draft, you have four options:

  - **Approve:** The draft is good. Click Approve. It will be sent automatically.
  - **Edit:** The draft is good but needs a personal touch. Click Edit, make your changes, and then Approve.
  - **Hold:** The draft is good but the timing is wrong. Click Hold to park it.
  - **Skip:** The touch doesn't make sense for this lead. Click Skip to advance the sequence without sending.

- **Your goal:** Get the queue to zero every day.

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
- **Don't push leads to GHL manually.** The system does this automatically when you approve the first touch.
- **Don't forget to mark manual DMs as sent.** This is the #1 failure point.
- **Don't engage in long back-and-forth conversations.** Your job is to book the demo. After 2-3 messages, push for the call.

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
