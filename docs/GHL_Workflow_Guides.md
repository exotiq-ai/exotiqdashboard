# GHL Workflow Build Guides -- Exotiq Operator Sales

These 5 workflows must be built in the GHL UI (Automation > Workflows).
Each guide has the exact trigger, conditions, and actions to configure.

---

## Workflow 1: New Lead Entry (Tag Routing)

**Purpose:** When a contact is created via webhook, route them to the correct pipeline stage based on their score tag.

**Trigger:** Contact Tag Added
- Tag: `exotiq-pipeline`

**Actions:**

1. **If/Else: Check for gregory-only tag**
   - Condition: Contact has tag `gregory-only`
   - YES branch:
     - Move Opportunity to stage: `Gregory -- Personal Outreach`
     - Send Internal Notification (Slack or email to Gregory):
       - Subject: "Score 5 Lead: {contact.name} / {contact.company}"
       - Body: "New Score 5 lead pushed to GHL. Call, don't DM. Check the dashboard for full intel."
   - NO branch:
     - **If/Else: Check for score-4 tag**
       - Condition: Contact has tag `score-4`
       - YES: Move Opportunity to stage: `DM Drafted`
       - NO: Move Opportunity to stage: `DM Drafted` (score-3 default)

2. **Create Task**
   - Title: "Review DM draft in custom field, send via IG"
   - Assigned to: LEx Team
   - Due: Same day

---

## Workflow 2: Follow-Up Timer

**Purpose:** Auto-advance leads through follow-up stages when no response is received after DM send.

**Trigger:** Opportunity Stage Changed
- Pipeline: Exotiq Operator Sales
- Stage: `DM Sent`

**Actions:**

1. **Wait** -- 5 days

2. **If/Else: Still in DM Sent?**
   - Condition: Opportunity stage = `DM Sent`
   - YES branch:
     - Move Opportunity to: `Follow-Up 1 Due`
     - Create Task:
       - Title: "Send Intel Drop follow-up to {contact.name}"
       - Assigned to: LEx Team
       - Due: Today
     
3. **Wait** -- 10 more days

4. **If/Else: Still in Follow-Up 1 Due (no response)?**
   - Condition: Opportunity stage = `Follow-Up 1 Due`
   - YES branch:
     - Move Opportunity to: `Follow-Up 2 Due`
     - Create Task:
       - Title: "Send Proof Point follow-up to {contact.name}"
       - Assigned to: LEx Team
       - Due: Today

5. **Wait** -- 10 more days

6. **If/Else: Still in Follow-Up 2 Due?**
   - Condition: Opportunity stage = `Follow-Up 2 Due`
   - YES branch:
     - Move Opportunity to: `Nurture`
     - Add Tag: `long-term-nurture`

---

## Workflow 3: Demo Confirmation Sequence

**Purpose:** Send confirmation and reminders when a demo is scheduled.

**Trigger:** Opportunity Stage Changed
- Pipeline: Exotiq Operator Sales
- Stage: `Demo Scheduled`

**Actions:**

1. **Immediately: Send Email**
   - Template: "Demo Confirmation"
   - Subject: "Confirmed: Your Exotiq Demo with Gregory"
   - Body: Include date/time, what to expect, Calendly reschedule link
   - From: Gregory's email

2. **Wait until** -- 1 day before the appointment
   - (Use appointment date from the contact's calendar event)

3. **Send Email**
   - Template: "Demo Reminder (Day Before)"
   - Subject: "Quick reminder: your Exotiq demo is tomorrow"
   - Body: Brief recap, include any relevant dashboard screenshot or fleet stats

4. **Wait until** -- 1 hour before appointment

5. **Send SMS**
   - Message: "Hey {first_name}, just a heads up, our call is in about an hour. Looking forward to it. -- Gregory"

6. **Wait** -- 30 minutes after scheduled end time

7. **If/Else: Was the appointment completed?**
   - If NOT completed (no-show):
     - Wait 24 hours
     - Send Email:
       - Subject: "Missed you -- let's reschedule"
       - Body: "Hey {first_name}, I think we missed each other. No worries. Here's my calendar if you want to grab another time: [Calendly link]"
     - Create Task: "Follow up on no-show: {contact.name}"

---

## Workflow 4: Post-Demo Follow-Up

**Purpose:** Automated follow-up sequence after a demo is completed.

**Trigger:** Opportunity Stage Changed
- Pipeline: Exotiq Operator Sales
- Stage: `Demo Complete`

**Actions:**

1. **Same day: Create Task**
   - Title: "Personalize post-demo recap email for {contact.name}"
   - Assigned to: Gregory
   - Due: Today
   - Note: "Review the email template in GHL before sending. Add specific talking points from the demo."

2. **Wait** -- 5 days

3. **If/Else: Opportunity still in Demo Complete?**
   - YES (no movement = no response to recap):
     - Send Email:
       - Template: "Proof Point Follow-Up"
       - Subject: "Quick update from Exotiq"
       - Body: Reference specific Tier 1 social proof (Jay/Denver, real numbers only)

4. **Wait** -- 7 more days (day 12)

5. **If/Else: Still in Demo Complete?**
   - YES:
     - Send Email:
       - Template: "Social Proof Follow-Up"
       - Subject: "What operators are saying"
       - Body: Include testimonial or case study snippet

6. **Wait** -- 9 more days (day 21)

7. **If/Else: Still in Demo Complete?**
   - YES:
     - Send Email:
       - Template: "Gentle Close"
       - Subject: "Last thought from Gregory"
       - Body: Founding Member pricing mention, urgency without pressure
     - Add Tag: `post-demo-sequence-complete`
     - If no response after 7 more days: Move to `Nurture`

---

## Workflow 5: Missed Call Text-Back

**Purpose:** Instantly text back when a pipeline contact calls and you miss it.

**Trigger:** Call Status
- Direction: Inbound
- Status: Missed / No Answer / Voicemail

**Conditions:**
- Contact has tag: `exotiq-pipeline`

**Actions:**

1. **Send SMS (immediately)**
   - Message: "Hey, this is Gregory from Exotiq. Just missed your call. I'll ring you right back, or grab a time here: https://calendly.com/hello-exotiq"

2. **Create Task**
   - Title: "Call back {contact.name} -- they called and we missed it"
   - Assigned to: Gregory
   - Due: Today
   - Priority: High

3. **Wait** -- 15 minutes

4. **Send Internal Notification**
   - To: Gregory (Slack or email)
   - Message: "Missed call from {contact.name} at {contact.company}. Text-back sent. Call them."

---

## Setup Notes

- All email templates should be created in GHL before activating the workflows
- Test each workflow with a dummy contact before going live
- The Follow-Up Timer and Post-Demo sequences have long wait steps. GHL will hold them in queue.
- For SMS: make sure you have LC Phone credits and the number is verified
- For the Demo Confirmation: this works best if you use GHL's built-in calendar (or connect Calendly)
- All copy in emails should follow DM Strategy V3 rules: no fabricated stats, Tier 1 and Tier 2 proof only
