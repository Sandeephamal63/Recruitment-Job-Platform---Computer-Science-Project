import { useEffect, useState } from 'react'
import { Avatar } from '@mui/material'
import { fetchCandidateAvatar, fetchOwnAvatar } from '@/api/profile'
import initials from '@/components/shared/initials'

interface AvatarImageProps {
  /**
   * The application this avatar belongs to (employer-facing surfaces). When set,
   * the bytes are read from the ownership-checked applicant route.
   *
   * When omitted the component reads the *signed-in candidate's own* avatar.
   * Those are the only two audiences the API serves, so exactly one of
   * `applicationId` and `ownAvatar` is meaningful per call site.
   */
  applicationId?: string
  ownAvatar?: boolean
  /**
   * Bumped by the owner after an upload or delete, to force a re-read.
   *
   * The own-avatar cache is the one entry that can go stale *within* a session:
   * the page loads, finds no photo, records that, and the candidate then picks a
   * photo — the bytes exist server-side but this component has already stopped
   * asking for them. Employer-facing rows have no such problem (a cached absence
   * is a documented, accepted trade-off), and the owner can be told to fix it, so
   * only this path gets an explicit way out. Including the epoch in the cache key
   * also covers re-uploading a file with the *same* name, which a name-based key
   * would miss.
   */
  epoch?: number
  /** Person's name; also the source of the fallback initials. */
  name: string
  /** Edge length in px. The image and the badge both fill it exactly. */
  size?: number
  /**
   * Accessible label. Defaults to the person's name; pass a more specific string
   * where a screen reader needs to know *which* person ("Priya Raman, applicant").
   */
  alt?: string
}

const OWN_PREFIX = 'own:'

const ownKey = (epoch: number) => `${OWN_PREFIX}v${epoch}`

/**
 * Resolved avatar object URLs, keyed by fetch key ("own:v0", or an application id).
 *
 * Deliberately module-level and deliberately never revoked on unmount. An
 * applicant table is 25 rows of this component; without the cache every
 * re-render and every page change would re-issue 25 authenticated requests, and
 * revoking on unmount would also throw away the result for a row that is merely
 * scrolled off. The images are capped at 1MB server-side and a session can only
 * ever view the applicants it has paged through, so the retained set is bounded
 * by that.
 *
 * The trade-off this accepts: an applicant who uploads a photo *after* an
 * employer has already looked at their application stays on initials for that
 * employer's session. Re-fetching on every render to avoid that is the worse
 * failure — a table of avatar-less applicants (the common case) would refetch
 * continuously. The owner's own view opts out via `epoch`.
 */
const objectUrlCache = new Map<string, string>()

/** Kinds of "there is no avatar" we have already established, so we stop asking. */
const missingCache = new Set<string>()

/**
 * Drop the own-avatar entries from superseded epochs, revoking their URLs.
 *
 * Employer rows are intentionally cached for the session, but the owner's is
 * re-read on every upload, so without this a candidate cycling through photos
 * would leak one blob per attempt for as long as the tab lives.
 */
function pruneSupersededOwnAvatars(currentEpoch: number) {
  const current = ownKey(currentEpoch)
  for (const [key, url] of objectUrlCache) {
    if (key.startsWith(OWN_PREFIX) && key !== current) {
      URL.revokeObjectURL(url)
      objectUrlCache.delete(key)
    }
  }
  for (const key of missingCache) {
    if (key.startsWith(OWN_PREFIX) && key !== current) missingCache.delete(key)
  }
}

const cacheKey = (applicationId: string | undefined, own: boolean | undefined, epoch: number) =>
  applicationId ?? (own ? ownKey(epoch) : '')

/**
 * A person's photo, or their initials when they have not uploaded one.
 *
 * Initials render immediately and are never replaced by a spinner: in a dense
 * applicant table a loading placeholder per row is worse than a monogram, and
 * the fallback is the state almost every candidate is in anyway. The image
 * fades in underneath once the fetch resolves.
 *
 * Distinct from `CompanyMark` in three ways that matter: a photo is
 * `cover`-fitted and circular (a logo is `contain`-fitted and rounded-square,
 * because logos are wider than they are tall and avatars are not), and the bytes
 * are a fetched blob rather than a public URL.
 */
export default function AvatarImage({
  applicationId,
  ownAvatar,
  epoch = 0,
  name,
  size = 40,
  alt,
}: AvatarImageProps) {
  const key = cacheKey(applicationId, ownAvatar, epoch)
  const [src, setSrc] = useState<string | null>(() => objectUrlCache.get(key) ?? null)

  useEffect(() => {
    if (ownAvatar) pruneSupersededOwnAvatars(epoch)

    if (!key || objectUrlCache.has(key) || missingCache.has(key)) {
      setSrc(objectUrlCache.get(key) ?? null)
      return
    }

    let active = true
    // `key` is empty unless exactly one of the two was passed, so one of these
    // two branches always has its argument.
    const load = applicationId ? fetchCandidateAvatar(applicationId) : fetchOwnAvatar()

    load
      .then((blob) => {
        if (!active) return
        const url = URL.createObjectURL(blob)
        objectUrlCache.set(key, url)
        setSrc(url)
      })
      .catch(() => {
        // 404 (no avatar), 403 (not this employer's applicant), or an expired
        // session. All of them mean the same thing to this component: show the
        // initials.
        if (!active) return
        missingCache.add(key)
        setSrc(null)
      })

    return () => {
      active = false
    }
  }, [key, applicationId, ownAvatar, epoch])

  // An image that decodes into nothing would show a broken-image glyph where a
  // face should be, so fall back the same way a failed fetch does.
  const onError = () => {
    missingCache.add(key)
    objectUrlCache.delete(key)
    setSrc(null)
  }

  return (
    <Avatar
      src={src ?? undefined}
      onError={src ? onError : undefined}
      alt={alt ?? name}
      sx={{
        width: size,
        height: size,
        bgcolor: 'primary.light',
        color: 'common.white',
        fontSize: Math.round(size * 0.36),
      }}
    >
      {initials(name)}
    </Avatar>
  )
}
