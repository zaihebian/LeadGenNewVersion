# Lead State Machine & System Logic Guide

This document explains how leads move through the system, how the inbox works, and what dashboard metrics mean.

## Table of Contents

1. [State Machine Overview](#state-machine-overview)
2. [State Details](#state-details)
3. [State Transitions](#state-transitions)
4. [Monitoring & Polling](#monitoring--polling)
5. [Dashboard Metrics](#dashboard-metrics)
6. [Inbox Filters](#inbox-filters)
7. [Common Scenarios](#common-scenarios)

---

## State Machine Overview

Leads progress through a series of states as they move through your outreach campaign. Here's the complete flow:

```
COLLECTED → ENRICHED → EMAILED_1 ────┐
                                      │
                          ┌───────────┼───────────┐
                          ↓           ↓           ↓
                    INTERESTED  NOT_INTERESTED  EMAILED_2
                          ↓           ↓           ↓
                          └───────→ CLOSED ←──────┘
```

### Quick State Summary

| State | Meaning | Duration | Auto Actions |
|-------|---------|----------|--------------|
| **COLLECTED** | Lead found, not yet enriched | Until enrichment | None |
| **ENRICHED** | LinkedIn data added, ready to email | Minutes | Email sent automatically |
| **EMAILED_1** | First email sent, waiting for reply | Up to 14 days | Reply monitoring, follow-up after 14 days |
| **INTERESTED** | Positive reply received | Forever | None (human takeover) |
| **NOT_INTERESTED** | Negative reply received | Forever | Polite follow-up sent automatically |
| **EMAILED_2** | Follow-up sent, waiting for reply | Indefinitely | Reply monitoring |
| **CLOSED** | Process complete | Forever | None |

---

## State Details

### COLLECTED
**What it means:** Lead has been found by the lead finder but hasn't been enriched with LinkedIn data yet.

**What happens:**
- Lead is collected from Apify leads-finder
- Waiting for LinkedIn enrichment

**Duration:** Usually seconds to minutes (depends on enrichment speed)

**Next state:** Automatically transitions to `ENRICHED` when LinkedIn posts are fetched

---

### ENRICHED
**What it means:** Lead has LinkedIn post data added and is ready to receive the first email.

**What happens:**
- LinkedIn posts fetched and stored
- Lead is ready for personalized email

**Duration:** Typically minutes (3-minute polling interval)

**Monitoring:** 
- **Email Sender Job** runs every **3 minutes**
- Automatically sends first email when ready
- Respects rate limits (max 50 emails/day, 2 min between emails)

**Next state:** Automatically transitions to `EMAILED_1` when first email is sent

---

### EMAILED_1
**What it means:** First email has been sent. The system is now waiting for a reply.

**What happens:**
- First personalized email sent to the lead
- System monitors for replies
- If no reply after 14 days, sends a follow-up

**Duration:** Up to 14 days (or until reply received)

**Monitoring:**
- **Reply Monitor Job** runs every **1 hour** - checks Gmail for new replies
- **Follow-up Sender Job** runs every **6 hours** - checks if 14 days have passed

**Possible outcomes:**
1. **Positive Reply** → Transitions to `INTERESTED`
2. **Negative Reply** → Transitions to `NOT_INTERESTED` (sends polite follow-up)
3. **Neutral Reply** → Stays in `EMAILED_1` (continues monitoring)
4. **No Reply (14 days)** → Sends follow-up → Transitions to `EMAILED_2`

**Reply Detection:**
- Checks Gmail inbox every hour
- Uses AI to classify reply sentiment (POSITIVE, NEGATIVE, NEUTRAL)
- Maximum delay: 1 hour (if reply arrives right after a check)

---

### INTERESTED
**What it means:** Lead replied with positive interest. Human takeover required.

**What happens:**
- Lead showed interest in your offer
- All automatic operations stop
- Thread marked as "requires human attention"
- You should respond manually

**Duration:** Forever (until manually closed)

**Monitoring:** None - this is a terminal state for human management

**Dashboard:** Counted in "Interested Leads" metric

**Inbox:** Appears in "Needs Attention" filter

**Next state:** Can be manually closed to `CLOSED` when done

---

### NOT_INTERESTED
**What it means:** Lead replied negatively (not interested, declined, etc.)

**What happens:**
1. System detects negative reply
2. Transitions to `NOT_INTERESTED`
3. **Automatically sends a polite follow-up** asking about their concerns
4. All automatic operations stop

**Duration:** Forever (until manually closed)

**Monitoring:** None - this is a terminal state

**Dashboard:** Counted in "Not Interested Leads" metric

**Inbox:** Does NOT appear in "Needs Attention" (only positive replies do)

**Next state:** Can be manually closed to `CLOSED` when done

---

### EMAILED_2
**What it means:** Follow-up email sent after 14 days of no reply. Still waiting for a response.

**What happens:**
- Lead didn't reply to first email within 14 days
- System automatically sent a follow-up email
- Now waiting for reply to the follow-up

**Duration:** Indefinitely (until reply received or manually closed)

**Monitoring:**
- **Reply Monitor Job** runs every **1 hour** - checks for replies
- No automatic closing (leads stay here until reply or manual action)

**Possible outcomes:**
1. **Any Reply Received** → Transitions to `CLOSED` (marked for review)
2. **No Reply** → Stays in `EMAILED_2` indefinitely

**Dashboard:** Counted in "Awaiting Reply" metric

**Inbox:** Appears in "Has Reply" filter if reply received

**Next state:** `CLOSED` if reply received, or stays forever if no reply

---

### CLOSED
**What it means:** Lead lifecycle is complete. No further automatic actions.

**What happens:**
- Lead reached a terminal state (INTERESTED, NOT_INTERESTED, or EMAILED_2 with reply)
- Manually closed or automatically closed after reply to follow-up
- All automatic operations stopped

**Duration:** Forever (final state)

**Monitoring:** None

**Dashboard:** Counted in "Closed Leads" metric

**Next state:** None (terminal state)

---

## State Transitions

### Automatic Transitions

| From | To | Trigger | Timing |
|------|-----|---------|--------|
| COLLECTED | ENRICHED | LinkedIn enrichment complete | Immediate |
| ENRICHED | EMAILED_1 | First email sent | Every 3 minutes (when ready) |
| EMAILED_1 | INTERESTED | Positive reply detected | Within 1 hour of reply |
| EMAILED_1 | NOT_INTERESTED | Negative reply detected | Within 1 hour of reply |
| EMAILED_1 | EMAILED_2 | No reply after 14 days | 14 days + up to 6 hours |
| EMAILED_2 | CLOSED | Reply received | Within 1 hour of reply |

### Manual Transitions

| From | To | How |
|------|-----|-----|
| INTERESTED | CLOSED | Manual close (via API/dashboard) |
| NOT_INTERESTED | CLOSED | Manual close (via API/dashboard) |
| EMAILED_2 | CLOSED | Manual close (via API/dashboard) |

---

## Monitoring & Polling

### Job Schedule

| Job | Frequency | Monitors | Action |
|-----|-----------|----------|--------|
| **Email Sender** | Every 3 minutes | `ENRICHED` leads | Sends first email |
| **Reply Monitor** | Every 1 hour | `EMAILED_1` and `EMAILED_2` leads | Checks Gmail for replies |
| **Follow-up Sender** | Every 6 hours | `EMAILED_1` leads (14+ days old) | Sends follow-up email |

### Monitoring Duration by State

- **COLLECTED**: No monitoring
- **ENRICHED**: Monitored every 3 minutes until email sent
- **EMAILED_1**: Monitored every hour for replies + every 6 hours for 14-day threshold
- **INTERESTED**: No monitoring (human takeover)
- **NOT_INTERESTED**: No monitoring (after follow-up sent)
- **EMAILED_2**: Monitored every hour for replies (indefinitely)
- **CLOSED**: No monitoring

### Reply Detection Timing

- **Check Frequency**: Every 1 hour
- **Maximum Delay**: 1 hour (if reply arrives right after a check)
- **Average Delay**: ~30 minutes
- **Detection Method**: Gmail API + AI sentiment classification

---

## Dashboard Metrics

### "Awaiting Reply"
**What it counts:** All leads in `EMAILED_1` or `EMAILED_2` state

**Important:** This includes leads that:
- ✅ Are waiting for their first reply (`EMAILED_1`)
- ✅ Are waiting for reply to follow-up (`EMAILED_2`)
- ⚠️ **May have already received replies** (still counted until state changes)

**Why:** Leads stay in these states until a reply is processed and state transitions. A lead with a reply that hasn't been processed yet will still show as "awaiting reply."

### "Replies Received"
**What it counts:** Number of unique leads that have at least one email thread with `has_reply = True`

**How it works:** Counts distinct lead IDs where any thread has received a reply

**Note:** This is a count of leads, not individual replies

### "Interested Leads"
**What it counts:** Leads in `INTERESTED` state

**Meaning:** Leads who replied positively and need human attention

### "Not Interested Leads"
**What it counts:** Leads in `NOT_INTERESTED` state

**Meaning:** Leads who replied negatively (polite follow-up already sent)

### "Closed Leads"
**What it counts:** Leads in `CLOSED` state

**Meaning:** Leads whose lifecycle is complete

### "Leads Contacted"
**What it counts:** Leads in `EMAILED_1`, `INTERESTED`, `NOT_INTERESTED`, `EMAILED_2`, or `CLOSED` states

**Meaning:** All leads that have received at least one email

---

## Inbox Filters

The inbox shows email threads (conversations) with leads. Each thread can be filtered:

### "All"
**Shows:** All email threads in the system

**Use case:** See everything

### "Needs Attention"
**Shows:** Threads where `requires_human = True`

**When is this set:**
- ✅ When lead receives **POSITIVE reply** → transitions to `INTERESTED`
- ✅ When lead in `EMAILED_2` receives **any reply** → transitions to `CLOSED`

**When is this NOT set:**
- ❌ Negative replies (transitions to `NOT_INTERESTED` but no flag)
- ❌ Neutral replies (stays in `EMAILED_1` but no flag)

**Meaning:** These are leads that need your immediate attention - either they're interested or replied to a follow-up

### "Has Reply"
**Shows:** Threads where `has_reply = True`

**When is this set:**
- ✅ **Any reply detected** (POSITIVE, NEGATIVE, or NEUTRAL)
- ✅ Set once and stays `True` forever

**Meaning:** Shows all conversations where the lead has responded at least once

**Note:** This includes all reply types, not just positive ones

---

## Common Scenarios

### Scenario 1: Happy Path - Positive Reply
1. Lead collected → `COLLECTED`
2. LinkedIn enriched → `ENRICHED`
3. Email sent (within 3 min) → `EMAILED_1`
4. Lead replies positively (detected within 1 hour) → `INTERESTED`
5. Thread appears in "Needs Attention" filter
6. You respond manually
7. (Optional) Close lead → `CLOSED`

**Timeline:** ~Minutes to hours

---

### Scenario 2: Negative Reply
1. Lead collected → `COLLECTED`
2. LinkedIn enriched → `ENRICHED`
3. Email sent → `EMAILED_1`
4. Lead replies negatively (detected within 1 hour) → `NOT_INTERESTED`
5. **System automatically sends polite follow-up** (asking about concerns)
6. Thread shows in "Has Reply" filter (but NOT "Needs Attention")
7. (Optional) Close lead → `CLOSED`

**Timeline:** ~Hours

---

### Scenario 3: No Reply - Follow-up Sent
1. Lead collected → `COLLECTED`
2. LinkedIn enriched → `ENRICHED`
3. Email sent → `EMAILED_1`
4. No reply for 14 days
5. System sends follow-up (checked every 6 hours) → `EMAILED_2`
6. Lead replies to follow-up (detected within 1 hour) → `CLOSED`
7. Thread appears in "Needs Attention" filter

**Timeline:** 14+ days

---

### Scenario 4: No Reply Ever
1. Lead collected → `COLLECTED`
2. LinkedIn enriched → `ENRICHED`
3. Email sent → `EMAILED_1`
4. No reply for 14 days
5. System sends follow-up → `EMAILED_2`
6. Still no reply → Stays in `EMAILED_2` forever
7. Dashboard shows as "Awaiting Reply"
8. (Optional) Manually close → `CLOSED`

**Timeline:** 14+ days, then indefinitely

---

### Scenario 5: Neutral Reply
1. Lead collected → `COLLECTED`
2. LinkedIn enriched → `ENRICHED`
3. Email sent → `EMAILED_1`
4. Lead replies neutrally (detected within 1 hour)
5. **Stays in `EMAILED_1`** (continues monitoring)
6. Thread shows in "Has Reply" filter
7. System continues checking for new replies
8. If another reply comes → Processed based on sentiment
9. If 14 days pass → Follow-up sent → `EMAILED_2`

**Timeline:** Hours to 14+ days

---

## Key Takeaways

### For Users

1. **"Awaiting Reply"** = Leads waiting for responses (may include some with replies not yet processed)
2. **"Needs Attention"** = Positive replies or follow-up replies (action required)
3. **"Has Reply"** = Any conversation with at least one reply
4. **Negative replies** automatically get a polite follow-up
5. **No reply after 14 days** = Automatic follow-up sent
6. **INTERESTED leads** = Stop all automation, human takeover required
7. **EMAILED_2 leads** = Can stay indefinitely if no reply

### For Developers

1. Reply detection happens every hour (maximum 1-hour delay)
2. Follow-up timing checked every 6 hours (14-day threshold)
3. Email sending happens every 3 minutes (respects rate limits)
4. Terminal states (INTERESTED, NOT_INTERESTED, CLOSED) have no automatic operations
5. EMAILED_2 is monitored indefinitely (no auto-close scheduled)

---

## Questions?

If you're confused about:
- **Why a lead is in a certain state** → Check the state details above
- **Why a metric shows a certain number** → Check the dashboard metrics section
- **Why a thread appears/doesn't appear in a filter** → Check the inbox filters section
- **How long something takes** → Check the monitoring & polling section

For technical details, see the code documentation in:
- `backend/app/services/state_machine.py`
- `backend/app/jobs/reply_monitor.py`
- `backend/app/jobs/followup_sender.py`
- `backend/app/api/routes/dashboard.py`
- `backend/app/api/routes/inbox.py`
