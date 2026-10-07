/**
 * Application-deadline display rules.
 *
 * A single derivation of "is this role still live, and how soon does it close"
 * for every surface that shows a vacancy. Four different components need this
 * answer and each re-deriving it is how a card would end up disagreeing with a
 * detail page about whether a role is still open.
 *
 * The server is authoritative — it excludes expired postings from browse, the
 * recommender and the apply path. This is presentation only, and it deliberately
 * computes "today" in **UTC** for the same reason the server stores a deadline
 * at the end of its day in UTC: a client in UTC-5 would otherwise call a role
 * expired several hours before the server does.
 */

const MS_PER_DAY = 86_400_000

/** Show a countdown close to the date, an absolute date further out. */
const RELATIVE_WINDOW_DAYS = 14
/** Inside this, the chip is emphasised (never as the only signal — the label says it). */
const URGENT_WINDOW_DAYS = 3

export interface DeadlineView {
  label: string
  expired: boolean
  urgent: boolean
}

/** Today on the server's clock, as `YYYY-MM-DD`. */
function todayUtc(): string {
  return new Date().toISOString().slice(0, 10)
}

function daysFromToday(deadline: string): number {
  const start = Date.parse(`${todayUtc()}T00:00:00Z`)
  const end = Date.parse(`${deadline}T00:00:00Z`)
  return Math.round((end - start) / MS_PER_DAY)
}

function formatAbsolute(deadline: string): string {
  // `YYYY-MM-DD` parses as UTC midnight, so without an explicit UTC time zone a
  // browser west of Greenwich would render the day *before* the deadline.
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(`${deadline}T00:00:00Z`))
}

/**
 * How to present a job's deadline, or `null` when it has none — a posting with
 * no closing date is open-ended, and callers render nothing rather than a chip
 * that implies an expiry that isn't there.
 */
export function deadlineView(deadline: string | null | undefined): DeadlineView | null {
  if (!deadline) return null

  const days = daysFromToday(deadline)
  if (days < 0) return { label: 'Deadline passed', expired: true, urgent: false }
  if (days === 0) return { label: 'Closes today', expired: false, urgent: true }
  if (days === 1) return { label: 'Closes tomorrow', expired: false, urgent: true }
  if (days <= RELATIVE_WINDOW_DAYS) {
    return { label: `Closes in ${days} days`, expired: false, urgent: days <= URGENT_WINDOW_DAYS }
  }
  return {
    label: `Closes ${formatAbsolute(deadline)}`,
    expired: false,
    urgent: false,
  }
}

/** The minimum selectable date in the job form, as `YYYY-MM-DD`. */
export function todayAsInputValue(): string {
  return todayUtc()
}
