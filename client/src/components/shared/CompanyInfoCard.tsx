import { Card, Chip, Stack, Typography } from '@mui/material'
import type { CardProps } from '@mui/material'
import CompanyMark from '@/components/shared/CompanyMark'
import { layout } from '@/theme'
import type { EmployerSummary } from '@/types/profile'

interface CompanyInfoCardProps {
  /** The joined company block, or null when there is nothing to show. */
  employer: EmployerSummary | null
  /** Merged over the card's own `sx`, so a caller can match the padding of the
   *  cards it sits beside — the public job page runs a coarser scale than
   *  `layout.cardPadding`. */
  sx?: CardProps['sx']
}

/**
 * The full company block: mark, name, industry, size, description.
 *
 * One component because the two surfaces that need it — a public job page and a
 * candidate's own application detail — are showing the same block of fields for
 * the same reason: a candidate deciding whether to apply, or checking afterwards
 * who they applied to, should not have to open the job to find out who is
 * hiring.
 *
 * Returns `null` when there is no employer attached. That is a normal state, not
 * an error: a job whose employer record is missing, or an application read
 * before the join resolved. The caller's own layout closes up rather than
 * rendering an empty shell.
 *
 * The list surfaces deliberately do *not* use this. `CompanyMark` alone is enough
 * there, and a description on every row of a list is noise.
 */
export default function CompanyInfoCard({ employer, sx }: CompanyInfoCardProps) {
  if (!employer) return null

  const facts = [employer.companyIndustry, employer.companySize].filter(Boolean)

  return (
    <Card variant="outlined" sx={{ p: layout.cardPadding, ...sx }}>
      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2, flexWrap: 'wrap', rowGap: 1 }}>
        <CompanyMark name={employer.companyName || employer.name} logoUrl={employer.companyLogoUrl} size={64} />
        <Stack sx={{ minWidth: 0 }}>
          <Typography variant="h6" component="h2">
            {employer.companyName || employer.name}
          </Typography>
          {facts.length > 0 && (
            <Stack direction="row" spacing={1} sx={{ mt: 1, flexWrap: 'wrap', rowGap: 1 }}>
              {facts.map((fact) => (
                <Chip key={fact} label={fact} size="small" variant="outlined" />
              ))}
            </Stack>
          )}
        </Stack>
      </Stack>

      {employer.companyDescription && (
        <Typography
          component="p"
          variant="body1"
          color="text.secondary"
          sx={{ whiteSpace: 'pre-line' }}
        >
          {employer.companyDescription}
        </Typography>
      )}
    </Card>
  )
}
