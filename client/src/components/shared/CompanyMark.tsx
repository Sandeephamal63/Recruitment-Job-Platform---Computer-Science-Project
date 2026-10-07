import { useEffect, useState } from 'react'
import { Box, Typography } from '@mui/material'
import { neutral } from '@/theme'
import { apiAssetUrl } from '@/api/client'
import initials from '@/components/shared/initials'

interface CompanyMarkProps {
  /** Company name; also the source of the fallback initials. */
  name: string
  /** API-root-relative logo path, or null/undefined when none was uploaded. */
  logoUrl?: string | null
  /** Box edge length in px. Both the image and the badge fill it exactly. */
  size?: number
  /**
   * Show the company name beside the mark. Used in the employer strip, where the
   * name is the point; elsewhere the name already sits beside it.
   */
  withName?: boolean
}

/**
 * A company's visual identity, from its logo when it has one and from its
 * initials when it doesn't.
 *
 * Logos are always rendered with the same fixed square and the image
 * `contain`-fitted, so a real logo and a fallback badge occupy identical space
 * and swapping one for the other never shifts the layout.
 *
 * A `companyLogoUrl` that fails to load also falls back to the initials. The
 * reference can outlive its file — the employer deleted the logo, the GridFS
 * object went missing, the employer record is gone — and a broken-image icon
 * sitting in the middle of the strip is far more conspicuous than a plain
 * monogram. The failed state resets when the URL changes so a corrected link
 * gets a fresh attempt.
 *
 * A candidate's photo is a different component (`AvatarImage`): it is
 * `cover`-fitted and circular rather than `contain`-fitted and rounded-square,
 * and it arrives as a fetched blob rather than a public URL.
 */
export default function CompanyMark({ name, logoUrl, size = 40, withName = false }: CompanyMarkProps) {
  const [logoFailed, setLogoFailed] = useState(false)

  useEffect(() => {
    setLogoFailed(false)
  }, [logoUrl])

  const box = {
    width: size,
    height: size,
    borderRadius: Math.round(size * 0.22),
    flexShrink: 0,
  } as const

  const mark = logoUrl && !logoFailed ? (
    <Box
      component="img"
      src={apiAssetUrl(logoUrl)}
      alt={`${name} logo`}
      onError={() => setLogoFailed(true)}
      sx={{
        ...box,
        objectFit: 'contain',
        backgroundColor: neutral[50],
        border: `1px solid ${neutral[200]}`,
      }}
    />
  ) : (
    <Box
      aria-hidden
      sx={{
        ...box,
        display: 'grid',
        placeItems: 'center',
        backgroundColor: neutral[100],
        border: `1px solid ${neutral[200]}`,
      }}
    >
      <Typography
        component="span"
        sx={{
          fontSize: Math.round(size * 0.36),
          fontWeight: 600,
          lineHeight: 1,
          color: neutral[700],
          letterSpacing: '0.01em',
          userSelect: 'none',
        }}
      >
        {initials(name)}
      </Typography>
    </Box>
  )

  if (!withName) {
    return mark
  }

  return (
    <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 1.25, minWidth: 0 }}>
      {mark}
      <Typography
        variant="body2"
        color="text.secondary"
        noWrap
        sx={{ minWidth: 0, maxWidth: 160, textOverflow: 'ellipsis', overflow: 'hidden' }}
      >
        {name}
      </Typography>
    </Box>
  )
}
