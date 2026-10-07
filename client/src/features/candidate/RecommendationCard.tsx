import {
  ArrowForwardRounded,
  CheckCircleOutlineRounded,
  HighlightOffRounded,
  LightbulbOutlined,
} from '@mui/icons-material'
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Stack,
  Typography,
} from '@mui/material'
import { scoreBand } from '@/features/matching/MatchReport'
import type { JobRecommendation } from '@/types/matching'

interface RecommendationCardProps {
  recommendation: JobRecommendation
  onViewJob: (jobId: string) => void
}

const MAX_SKILLS = 4

/**
 * One recommended job, shown with the reasoning behind its score rather than the
 * score alone.
 *
 * The number is the point: this is a ranking the candidate can check. Showing
 * "72%" with no explanation would be a number the product cannot defend, so the
 * matched and missing skills are on the card and the band label sits beside the
 * score — colour is never the only signal.
 */
export default function RecommendationCard({
  recommendation,
  onViewJob,
}: RecommendationCardProps) {
  const { jobTitle, companyName, matchScore, matchedSkills, missingSkills } = recommendation
  const band = scoreBand(matchScore)
  const visibleMatched = matchedSkills.slice(0, MAX_SKILLS)
  const hiddenMatched = matchedSkills.length - visibleMatched.length

  return (
    <Card
      variant="outlined"
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        borderLeftWidth: 4,
        borderLeftColor: `${band.color}.main`,
        transition: 'box-shadow 0.2s',
        '&:hover': { boxShadow: 3 },
      }}
    >
      <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column', p: { xs: 2, sm: 2.5 }, '&:last-child': { pb: 2 } }}>
        <Stack direction="row" spacing={1} justifyContent="space-between" alignItems="flex-start" sx={{ mb: 0.5 }}>
          <Typography variant="subtitle1" fontWeight={600}>
            {jobTitle || 'Job'}
          </Typography>
          <Stack direction="row" spacing={0.5} alignItems="baseline" sx={{ flexShrink: 0 }}>
            <Typography variant="h6" sx={{ fontWeight: 800, color: `${band.color}.main`, lineHeight: 1 }}>
              {matchScore}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              / 100
            </Typography>
          </Stack>
        </Stack>

        <Typography variant="caption" sx={{ color: `${band.color}.main`, fontWeight: 600 }}>
          {band.label}
        </Typography>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          {companyName || 'Unknown Company'}
        </Typography>

        <Stack spacing={1} sx={{ flex: 1 }}>
          {visibleMatched.length > 0 && (
            <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap', rowGap: 0.5, alignItems: 'center' }}>
              <CheckCircleOutlineRounded fontSize="small" color="success" />
              {visibleMatched.map((skill) => (
                <Chip key={skill} label={skill} size="small" variant="outlined" color="success" />
              ))}
              {hiddenMatched > 0 && (
                <Chip label={`+${hiddenMatched} more`} size="small" variant="outlined" />
              )}
            </Stack>
          )}
          {missingSkills.length > 0 && (
            <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap', rowGap: 0.5, alignItems: 'center' }}>
              <HighlightOffRounded fontSize="small" color="error" />
              {missingSkills.slice(0, MAX_SKILLS).map((skill) => (
                <Chip key={skill} label={skill} size="small" variant="outlined" />
              ))}
            </Stack>
          )}
        </Stack>

        {recommendation.recommendations.length > 0 && (
          <Box sx={{ mt: 1.5 }}>
            <Stack direction="row" spacing={0.5} alignItems="flex-start">
              <LightbulbOutlined fontSize="small" color="warning" sx={{ mt: 0.25 }} />
              <Typography variant="caption" color="text.secondary">
                {recommendation.recommendations[0]}
              </Typography>
            </Stack>
          </Box>
        )}

        <Button
          variant="contained"
          size="small"
          endIcon={<ArrowForwardRounded />}
          onClick={() => onViewJob(recommendation.jobId)}
          sx={{ mt: 2, alignSelf: 'flex-start' }}
        >
          View Job
        </Button>
      </CardContent>
    </Card>
  )
}
