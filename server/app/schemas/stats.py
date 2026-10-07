from marshmallow import fields

from .base import BaseSchema


class StageCountsSchema(BaseSchema):
    """Count of applications in each funnel stage for one job."""

    submitted = fields.Integer()
    underReview = fields.Integer()
    shortlisted = fields.Integer()
    rejected = fields.Integer()
    withdrawn = fields.Integer()
    total = fields.Integer()
    averageScore = fields.Function(lambda stats: stats.get("averageScore"))


class JobFunnelSchema(BaseSchema):
    """Per-row funnel for the employer job list (GET /api/jobs/mine/stats)."""

    jobId = fields.Str()
    title = fields.Str()
    status = fields.Str()
    stages = fields.Function(lambda entry: entry["stages"])


class EmployerOverviewSchema(BaseSchema):
    """Headline counters for the employer dashboard."""

    openJobs = fields.Integer()
    closedJobs = fields.Integer()
    totalApplicants = fields.Integer()
    shortlisted = fields.Integer()
    averageScore = fields.Function(lambda overview: overview.get("averageScore"))


class ScoreBandSchema(BaseSchema):
    """One bucket of the applicant score distribution."""

    band = fields.Str()
    count = fields.Integer()


class ScoreDistributionSchema(BaseSchema):
    """Histogram of match scores across an employer's applicants, used to show
    the spread of fit instead of a single average."""

    buckets = fields.Function(lambda distribution: distribution["buckets"])
    total = fields.Integer()


class CandidateScoreDistributionSchema(BaseSchema):
    """Score distribution of a single job's applicant pool."""

    jobId = fields.Str()
    buckets = fields.Function(lambda distribution: distribution["buckets"])
    total = fields.Integer()
    average = fields.Function(lambda distribution: distribution.get("average"))


job_funnel_schema = JobFunnelSchema()
employer_overview_schema = EmployerOverviewSchema()
score_distribution_schema = ScoreDistributionSchema()
candidate_score_distribution_schema = CandidateScoreDistributionSchema()
stage_counts_schema = StageCountsSchema()

__all__ = [
    "CandidateScoreDistributionSchema",
    "EmployerOverviewSchema",
    "JobFunnelSchema",
    "ScoreBandSchema",
    "ScoreDistributionSchema",
    "StageCountsSchema",
    "candidate_score_distribution_schema",
    "employer_overview_schema",
    "job_funnel_schema",
    "score_distribution_schema",
    "stage_counts_schema",
]
