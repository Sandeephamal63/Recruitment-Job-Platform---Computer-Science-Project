import {
  CheckCircleOutlineRounded,
  HighlightOffRounded,
  InsightsOutlined,
  LightbulbOutlined,
} from '@mui/icons-material'
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Stack,
  Typography,
} from '@mui/material'
import type { MatchResult } from '@/types/matching'

/**
 * Score bands. This table is the single definition of what a match score means
 * across the whole app.
 *
 * There used to be two components rendering the same `matchResults.matchScore`
 * with two different verdicts: the applicant list called ≥70 a "Strong fit"
 * while the applicant detail called ≥80 a "Strong match" and ≥60 a "Good
 * match". An employer comparing a row against the page it opens got a
 * contradictory answer for the same number. Anything that needs a band reads
 * `scoreBand` from here.
 */
export type MatchBand = {
  min: number
  label: string
  color: 'success' | 'info' | 'warning' | 'error'
}

const BANDS: MatchBand[] = [
  { min: 80, label: 'Strong match', color: 'success' },
  { min: 60, label: 'Good match', color: 'info' },
  { min: 40, label: 'Reasonable match', color: 'warning' },
  { min: 0, label: 'Low match', color: 'error' },
]

export function scoreBand(score: number): MatchBand {
  return BANDS.find((band) => score >= band.min) ?? BANDS[BANDS.length - 1]
}

interface MatchReportProps {
  matchResult?: MatchResult | null
  /** `compact` is a single line for table rows and list cards. */
  variant?: 'compact' | 'full'
  loading?: boolean
  error?: string | null
  onRetry?: () => void
}

/**
 * Renders a stored match result. Colour is never the only signal — the numeric
 * score and the band's label are always shown next to it, so the reading does
 * not depend on distinguishing green from amber.
 */
export default function MatchReport({
  matchResult,
  variant = 'full',
  loading = false,
  error = null,
  onRetry,
}: MatchReportProps) {
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
        <CircularProgress size={28} />
      </Box>
    )
  }

  if (error) {
    return (
      <Alert
        severity="error"
        action={
          onRetry && (
            <Button color="inherit" size="small" onClick={onRetry}>
              Retry
            </Button>
          )
        }
      >
        Could not load the match report. {error}
      </Alert>
    )
  }

  if (!matchResult) return null

  if (matchResult.matchScore === null) {
    if (variant === 'compact') {
      return (
        <Typography variant="caption" color="text.secondary">
          Pending
        </Typography>
      )
    }
    return (
      <Stack spacing={1.5} alignItems="flex-start">
        <Stack direction="row" spacing={1} alignItems="center">
          <InsightsOutlined color="action" />
          <Typography variant="subtitle1">Match report pending</Typography>
        </Stack>
        <Typography variant="body2" color="text.secondary">
          The analysis hasn&apos;t finished running yet. Check back in a moment.
        </Typography>
        {onRetry && (
          <Button size="small" variant="outlined" onClick={onRetry}>
            Refresh report
          </Button>
        )}
      </Stack>
    )
  }

  const band = scoreBand(matchResult.matchScore)

  if (variant === 'compact') {
    return (
      <Stack direction="row" spacing={0.75} alignItems="baseline">
        <Typography variant="subtitle1" sx={{ fontWeight: 700, color: `${band.color}.main`, lineHeight: 1 }}>
          {matchResult.matchScore}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {band.label}
        </Typography>
      </Stack>
    )
  }

  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={2} alignItems="center" sx={{ flexWrap: 'wrap', rowGap: 1 }}>
        <Box>
          <Stack direction="row" alignItems="baseline" spacing={0.5}>
            <Typography variant="h3" sx={{ fontWeight: 800, color: `${band.color}.main`, lineHeight: 1 }}>
              {matchResult.matchScore}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              / 100
            </Typography>
          </Stack>
          <Typography variant="subtitle2" sx={{ color: `${band.color}.main` }}>
            {band.label}
          </Typography>
        </Box>
        <Stack spacing={1} sx={{ flexGrow: 1, minWidth: 0 }}>
          {matchResult.matchedSkills.length > 0 && (
            <Stack direction="row" spacing={0.75} sx={{ flexWrap: 'wrap', rowGap: 0.5, alignItems: 'center' }}>
              <CheckCircleOutlineRounded fontSize="small" color="success" />
              {matchResult.matchedSkills.map((skill) => (
                <Chip key={skill} label={skill} size="small" variant="outlined" color="success" sx={{ mb: 0.5 }} />
              ))}
            </Stack>
          )}
          {matchResult.missingSkills.length > 0 && (
            <Stack direction="row" spacing={0.75} sx={{ flexWrap: 'wrap', rowGap: 0.5, alignItems: 'center' }}>
              <HighlightOffRounded fontSize="small" color="error" />
              {matchResult.missingSkills.map((skill) => (
                <Chip key={skill} label={skill} size="small" variant="outlined" color="default" sx={{ mb: 0.5 }} />
              ))}
            </Stack>
          )}
        </Stack>
      </Stack>
      {matchResult.recommendations.length > 0 && (
        <Stack spacing={1}>
          <Stack direction="row" spacing={1} alignItems="center">
            <LightbulbOutlined fontSize="small" color="warning" />
            <Typography variant="subtitle2">Recommendations</Typography>
          </Stack>
          {matchResult.recommendations.map((recommendation, index) => (
            <Typography key={index} variant="body2" color="text.secondary">
              {recommendation}
            </Typography>
          ))}
        </Stack>
      )}
      <Typography variant="caption" color="text.disabled">
        Scored with {matchResult.modelVersion}
        {matchResult.createdAt ? ` · ${new Date(matchResult.createdAt).toLocaleDateString()}` : ''}
      </Typography>
    </Stack>
  )
}
