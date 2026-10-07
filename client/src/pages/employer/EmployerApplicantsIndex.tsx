import * as applicationsApi from "@/api/applications";
import { getErrorMessage } from "@/api/errors";
import { listMyJobs } from "@/api/jobs";
import PageLayout from "@/components/portal/PageLayout";
import AvatarImage from "@/components/shared/AvatarImage";
import MatchReport from "@/features/matching/MatchReport";
import { useToast } from "@/hooks/useToast";
import { neutral } from "@/theme";
import type { Application, ApplicationStatus } from "@/types/application";
import type { Job } from "@/types/jobs";
import {
  CheckCircleOutlineRounded,
  ClearRounded,
  DownloadRounded,
  FilterListRounded,
  PeopleRounded,
  SearchRounded,
  TrendingUpRounded,
  WorkOutlineRounded,
} from "@mui/icons-material";
import {
  Alert,
  Avatar,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import Grid from "@mui/material/Grid2";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link as RouterLink } from "react-router-dom";

const STATUS_OPTIONS: { value: ApplicationStatus; label: string }[] = [
  { value: "submitted", label: "Submitted" },
  { value: "under_review", label: "Under review" },
  { value: "shortlisted", label: "Shortlisted" },
  { value: "rejected", label: "Rejected" },
  { value: "withdrawn", label: "Withdrawn" },
];

const SORT_OPTIONS = [
  { value: "newest", label: "Newest first" },
  { value: "oldest", label: "Oldest first" },
  { value: "score-desc", label: "Score: High to Low" },
  { value: "score-asc", label: "Score: Low to High" },
];

function StatusChip({ status }: { status: ApplicationStatus }) {
  const configs: Record<
    ApplicationStatus,
    {
      label: string;
      color: "default" | "info" | "success" | "error" | "warning";
      bg?: string;
    }
  > = {
    submitted: { label: "Submitted", color: "default" },
    under_review: { label: "Under Review", color: "info" },
    shortlisted: { label: "Shortlisted", color: "success" },
    rejected: { label: "Rejected", color: "error" },
    withdrawn: { label: "Withdrawn", color: "warning" },
  };
  const config = configs[status] ?? { label: status, color: "default" };

  return (
    <Chip
      label={config.label}
      size="small"
      color={config.color}
      variant="outlined"
      sx={{ fontWeight: 600, height: 24, fontSize: "0.75rem" }}
    />
  );
}

function StatusUpdateDialog({
  open,
  onClose,
  application,
  onStatusChange,
  loading,
}: {
  open: boolean;
  onClose: () => void;
  application: Application;
  onStatusChange: (
    application: Application,
    status: ApplicationStatus,
    reason?: string,
  ) => Promise<void>;
  loading: boolean;
}) {
  const [status, setStatus] = useState<ApplicationStatus>(application.status);
  const [showReason, setShowReason] = useState(false);
  const [reason, setReason] = useState(application.rejectionReason || "");

  const requiresReason = status === "rejected";

  const handleSubmit = async () => {
    if (requiresReason && !reason.trim()) {
      setShowReason(true);
      return;
    }
    await onStatusChange(
      application,
      status,
      requiresReason ? reason.trim() : undefined,
    );
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ fontWeight: 700 }}>
        Update status for {application.candidate?.name || "Applicant"}
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Applying for: <strong>{application.job?.title || "Job"}</strong>
        </Typography>

        <FormControl fullWidth sx={{ mt: 1, mb: 2 }}>
          <InputLabel id="status-label">Stage</InputLabel>
          <Select
            labelId="status-label"
            value={status}
            label="Stage"
            onChange={(e) => {
              const newStatus = e.target.value as ApplicationStatus;
              setStatus(newStatus);
              setShowReason(newStatus === "rejected");
            }}
          >
            {STATUS_OPTIONS.filter((s) => s.value !== "withdrawn").map(
              (opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ),
            )}
          </Select>
        </FormControl>

        {showReason && (
          <TextField
            multiline
            rows={3}
            fullWidth
            label="Rejection reason (required)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Explain why this candidate was not selected..."
            sx={{ mt: 1 }}
            error={requiresReason && !reason.trim()}
            helperText={
              requiresReason && !reason.trim()
                ? "A rejection reason is required"
                : undefined
            }
          />
        )}
      </DialogContent>
      <DialogActions sx={{ flexDirection: { xs: 'column-reverse', sm: 'row' }, gap: 1, px: 2, pb: 2 }}>
        <Button onClick={onClose} disabled={loading} color="inherit" sx={{ width: { xs: '100%', sm: 'auto' } }}>
          Cancel
        </Button>
        <Button
          variant="contained"
          color={status === "rejected" ? "error" : "primary"}
          onClick={handleSubmit}
          disabled={loading}
          sx={{ width: { xs: '100%', sm: 'auto' } }}
        >
          {loading
            ? "Updating..."
            : status === "rejected"
              ? "Reject"
              : "Update Status"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default function EmployerApplicantsIndex() {
  const toast = useToast();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string>("all");
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [filterStatus, setFilterStatus] = useState<ApplicationStatus | "">("");
  const [minScore, setMinScore] = useState<number | "">("");
  const [sort, setSort] = useState<string>("newest");

  // Pagination
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);

  // Dialog & Action States
  const [statusDialog, setStatusDialog] = useState<{
    open: boolean;
    application: Application | null;
  }>({
    open: false,
    application: null,
  });
  const [updatingStatus, setUpdatingStatus] = useState(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  // Load all jobs posted by this employer
  const loadInitialData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const employerJobs = await listMyJobs();
      setJobs(employerJobs);

      if (employerJobs.length === 0) {
        setApplications([]);
        setLoading(false);
        return;
      }

      // Fetch all applicants across all jobs
      const results = await Promise.all(
        employerJobs.map(async (job) => {
          try {
            const resp = await applicationsApi.listApplicants({
              jobId: job.id,
              pageSize: 100,
            });
            return resp.applications.map((app) => ({
              ...app,
              job: app.job || job,
            }));
          } catch {
            return [];
          }
        }),
      );

      setApplications(results.flat());
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Status Change Handler
  const handleStatusChange = async (
    application: Application,
    newStatus: ApplicationStatus,
    reason?: string,
  ) => {
    setUpdatingStatus(true);
    try {
      await applicationsApi.updateApplicationStatus(
        application.id,
        newStatus,
        reason,
      );
      setApplications((prev) =>
        prev.map((app) =>
          app.id === application.id
            ? {
                ...app,
                status: newStatus,
                rejectionReason: reason ?? app.rejectionReason,
              }
            : app,
        ),
      );
      toast.success(`Applicant moved to ${newStatus.replace("_", " ")}.`);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setUpdatingStatus(false);
    }
  };

  // CV Download Handler
  const handleDownloadCv = async (application: Application) => {
    setDownloadingId(application.id);
    try {
      const blob = await applicationsApi.downloadCv(application.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download =
        application.cvFileName ||
        `${application.candidate?.name || "applicant"}-cv.pdf`;
      link.click();
      URL.revokeObjectURL(url);
      toast.info("CV download started.");
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setDownloadingId(null);
    }
  };

  // Filtered & Sorted Applications
  const filteredApplications = useMemo(() => {
    return applications
      .filter((app) => {
        // Job Filter
        if (selectedJobId !== "all" && app.jobId !== selectedJobId) {
          return false;
        }
        // Status Filter
        if (filterStatus && app.status !== filterStatus) {
          return false;
        }
        // Min Score Filter
        if (minScore !== "") {
          const score = app.match?.matchScore ?? -1;
          if (score < minScore) return false;
        }
        // Search Query
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          const name = app.candidate?.name?.toLowerCase() || "";
          const email = app.candidate?.email?.toLowerCase() || "";
          const headline = app.candidate?.headline?.toLowerCase() || "";
          const jobTitle = app.job?.title?.toLowerCase() || "";
          const skills = (app.candidate?.skills || []).join(" ").toLowerCase();
          return (
            name.includes(q) ||
            email.includes(q) ||
            headline.includes(q) ||
            jobTitle.includes(q) ||
            skills.includes(q)
          );
        }
        return true;
      })
      .sort((a, b) => {
        if (sort === "score-desc") {
          return (b.match?.matchScore ?? -1) - (a.match?.matchScore ?? -1);
        }
        if (sort === "score-asc") {
          return (a.match?.matchScore ?? 101) - (b.match?.matchScore ?? 101);
        }
        if (sort === "oldest") {
          return (
            new Date(a.submittedAt).getTime() -
            new Date(b.submittedAt).getTime()
          );
        }
        // Default: newest
        return (
          new Date(b.submittedAt).getTime() - new Date(a.submittedAt).getTime()
        );
      });
  }, [applications, selectedJobId, filterStatus, minScore, searchQuery, sort]);

  // KPIs
  const totalCount = applications.length;
  const shortlistedCount = applications.filter(
    (a) => a.status === "shortlisted",
  ).length;
  const underReviewCount = applications.filter(
    (a) => a.status === "under_review",
  ).length;
  const averageScore = useMemo(() => {
    const scored = applications.filter((a) => a.match?.matchScore != null);
    if (!scored.length) return null;
    const sum = scored.reduce((acc, a) => acc + (a.match?.matchScore ?? 0), 0);
    return Math.round(sum / scored.length);
  }, [applications]);

  // Paged items
  const pagedApplications = useMemo(() => {
    const start = page * pageSize;
    return filteredApplications.slice(start, start + pageSize);
  }, [filteredApplications, page, pageSize]);

  const clearFilters = () => {
    setSelectedJobId("all");
    setFilterStatus("");
    setMinScore("");
    setSearchQuery("");
    setSort("newest");
    setPage(0);
  };

  const hasActiveFilters =
    selectedJobId !== "all" ||
    filterStatus !== "" ||
    minScore !== "" ||
    searchQuery !== "";

  return (
    <PageLayout
      title="Applicants"
      subtitle="Review, filter, and track all candidates across your active and previous job postings."
    >
      {/* KPI Cards Banner */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 6, sm: 3 }}>
          <Card sx={{ p: 2, display: "flex", alignItems: "center", gap: 2 }}>
            <Avatar sx={{ bgcolor: "primary.light", width: 44, height: 44 }}>
              <PeopleRounded />
            </Avatar>
            <Box>
              <Typography
                variant="caption"
                color="text.secondary"
                fontWeight={500}
              >
                Total Applicants
              </Typography>
              <Typography variant="h5" fontWeight={700}>
                {totalCount}
              </Typography>
            </Box>
          </Card>
        </Grid>

        <Grid size={{ xs: 6, sm: 3 }}>
          <Card sx={{ p: 2, display: "flex", alignItems: "center", gap: 2 }}>
            <Avatar
              sx={{
                bgcolor: "#EAF6EE",
                color: "#2F7D4F",
                width: 44,
                height: 44,
              }}
            >
              <CheckCircleOutlineRounded />
            </Avatar>
            <Box>
              <Typography
                variant="caption"
                color="text.secondary"
                fontWeight={500}
              >
                Shortlisted
              </Typography>
              <Typography
                variant="h5"
                fontWeight={700}
                sx={{ color: "#2F7D4F" }}
              >
                {shortlistedCount}
              </Typography>
            </Box>
          </Card>
        </Grid>

        <Grid size={{ xs: 6, sm: 3 }}>
          <Card sx={{ p: 2, display: "flex", alignItems: "center", gap: 2 }}>
            <Avatar
              sx={{
                bgcolor: "#EFF8FF",
                color: "#175CD3",
                width: 44,
                height: 44,
              }}
            >
              <WorkOutlineRounded />
            </Avatar>
            <Box>
              <Typography
                variant="caption"
                color="text.secondary"
                fontWeight={500}
              >
                Under Review
              </Typography>
              <Typography
                variant="h5"
                fontWeight={700}
                sx={{ color: "#175CD3" }}
              >
                {underReviewCount}
              </Typography>
            </Box>
          </Card>
        </Grid>

        <Grid size={{ xs: 6, sm: 3 }}>
          <Card sx={{ p: 2, display: "flex", alignItems: "center", gap: 2 }}>
            <Avatar
              sx={{
                bgcolor: "#FFF4ED",
                color: "#B4551F",
                width: 44,
                height: 44,
              }}
            >
              <TrendingUpRounded />
            </Avatar>
            <Box>
              <Typography
                variant="caption"
                color="text.secondary"
                fontWeight={500}
              >
                Avg Match Score
              </Typography>
              <Typography
                variant="h5"
                fontWeight={700}
                sx={{ color: "#B4551F" }}
              >
                {averageScore != null ? `${averageScore}%` : "—"}
              </Typography>
            </Box>
          </Card>
        </Grid>
      </Grid>

      {/* Main Container Card */}
      <Card variant="outlined" sx={{ p: { xs: 2, sm: 3 }, overflow: "hidden" }}>
        {/* Filters and Search Bar */}
        <Stack spacing={2} sx={{ mb: 3 }}>
          <Stack
            direction={{ xs: "column", md: "row" }}
            spacing={1.5}
            alignItems={{ xs: "stretch", md: "center" }}
            justifyContent="space-between"
          >
            {/* Search Input */}
            <TextField
              size="small"
              placeholder="Search candidate name, email, skills..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setPage(0);
              }}
              slotProps={{
                input: {
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchRounded
                        sx={{ color: "text.disabled", fontSize: 20 }}
                      />
                    </InputAdornment>
                  ),
                  endAdornment: searchQuery ? (
                    <InputAdornment position="end">
                      <IconButton
                        size="small"
                        onClick={() => setSearchQuery("")}
                      >
                        <ClearRounded sx={{ fontSize: 16 }} />
                      </IconButton>
                    </InputAdornment>
                  ) : null,
                },
              }}
              sx={{ minWidth: { xs: "100%", md: 320 } }}
            />

            {/* Filter Dropdowns */}
            <Stack
              direction={{ xs: "column", sm: "row" }}
              spacing={1.5}
              alignItems="center"
              flexWrap="wrap"
            >
              {/* Job Selector */}
              <FormControl
                size="small"
                sx={{ minWidth: 180, width: { xs: "100%", sm: "auto" } }}
              >
                <InputLabel id="job-filter-label">Job Posting</InputLabel>
                <Select
                  labelId="job-filter-label"
                  value={selectedJobId}
                  label="Job Posting"
                  onChange={(e) => {
                    setSelectedJobId(e.target.value);
                    setPage(0);
                  }}
                >
                  <MenuItem value="all">All Jobs ({jobs.length})</MenuItem>
                  {jobs.map((job) => (
                    <MenuItem key={job.id} value={job.id}>
                      {job.title}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {/* Status Filter */}
              <FormControl
                size="small"
                sx={{ minWidth: 150, width: { xs: "100%", sm: "auto" } }}
              >
                <InputLabel id="status-filter-label">Status</InputLabel>
                <Select
                  labelId="status-filter-label"
                  value={filterStatus}
                  label="Status"
                  onChange={(e) => {
                    setFilterStatus(e.target.value as ApplicationStatus);
                    setPage(0);
                  }}
                >
                  <MenuItem value="">All Statuses</MenuItem>
                  {STATUS_OPTIONS.map((opt) => (
                    <MenuItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {/* Min Score Filter */}
              <TextField
                size="small"
                type="number"
                label="Min Score"
                value={minScore}
                placeholder="0-100"
                onChange={(e) => {
                  setMinScore(
                    e.target.value === "" ? "" : Number(e.target.value),
                  );
                  setPage(0);
                }}
                slotProps={{ htmlInput: { min: 0, max: 100, step: 5 } }}
                sx={{ width: { xs: "100%", sm: 110 } }}
              />

              {/* Sort By */}
              <FormControl
                size="small"
                sx={{ minWidth: 170, width: { xs: "100%", sm: "auto" } }}
              >
                <InputLabel id="sort-select-label">Sort</InputLabel>
                <Select
                  labelId="sort-select-label"
                  value={sort}
                  label="Sort"
                  onChange={(e) => {
                    setSort(e.target.value);
                    setPage(0);
                  }}
                >
                  {SORT_OPTIONS.map((opt) => (
                    <MenuItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {hasActiveFilters && (
                <Button size="small" onClick={clearFilters} color="secondary">
                  Reset
                </Button>
              )}
            </Stack>
          </Stack>
        </Stack>

        {/* Loading State */}
        {loading && (
          <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
            <CircularProgress />
          </Box>
        )}

        {/* Error Alert */}
        {!loading && error && (
          <Alert
            severity="error"
            action={
              <Button color="inherit" size="small" onClick={loadInitialData}>
                Retry
              </Button>
            }
            sx={{ mb: 2 }}
          >
            {error}
          </Alert>
        )}

        {/* Empty States */}
        {!loading && !error && jobs.length === 0 && (
          <Box sx={{ py: 6, textAlign: "center" }}>
            <Typography variant="h6" fontWeight={600} gutterBottom>
              No job postings created yet
            </Typography>
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ mb: 2.5, maxWidth: 440, mx: "auto" }}
            >
              Create a job posting to start receiving applications and matching
              scores from qualified candidates.
            </Typography>
            <Button
              component={RouterLink}
              to="/employer/jobs/new"
              variant="contained"
            >
              Post a Job
            </Button>
          </Box>
        )}

        {!loading &&
          !error &&
          jobs.length > 0 &&
          filteredApplications.length === 0 && (
            <Box sx={{ py: 6, textAlign: "center" }}>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                {hasActiveFilters
                  ? "No matching applicants"
                  : "No applicants yet"}
              </Typography>
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ mb: 2, maxWidth: 440, mx: "auto" }}
              >
                {hasActiveFilters
                  ? "Try adjusting or clearing your filters to see more candidate applications."
                  : "Candidates who apply to your job postings will appear here along with their automated match reports."}
              </Typography>
              {hasActiveFilters && (
                <Button variant="outlined" size="small" onClick={clearFilters}>
                  Clear All Filters
                </Button>
              )}
            </Box>
          )}

        {/* Applicants Data Table */}
        {!loading && !error && filteredApplications.length > 0 && (
          <>
            <Box sx={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch', border: `1px solid ${neutral[200]}`, borderRadius: 1.5 }}>
            <TableContainer
              sx={{ border: 'none', borderRadius: 0 }}
            >
              <Table size="medium" sx={{ minWidth: 800 }}>
                <TableHead sx={{ bgcolor: neutral[50] }}>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Candidate</TableCell>
                    <TableCell sx={{ fontWeight: 600, display: { xs: 'none', sm: 'table-cell' } }}>Job Applied</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Match Score</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
                    <TableCell sx={{ fontWeight: 600, display: { xs: 'none', sm: 'table-cell' } }}>Submitted</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600 }}>
                      Actions
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {pagedApplications.map((app) => {
                    const candidateName = app.candidate?.name || "Applicant";

                    return (
                      <TableRow
                        key={app.id}
                        hover
                        sx={{ "&:last-child td": { borderBottom: 0 } }}
                      >
                        {/* Candidate Column */}
                        <TableCell>
                          <Stack
                            direction="row"
                            spacing={1.5}
                            alignItems="center"
                          >
                            <AvatarImage
                              applicationId={app.id}
                              name={candidateName}
                              size={34}
                              alt=""
                            />
                            <Box sx={{ minWidth: 0 }}>
                              <Typography
                                variant="body2"
                                fontWeight={600}
                                noWrap
                              >
                                {candidateName}
                              </Typography>
                              <Typography
                                variant="caption"
                                color="text.secondary"
                                noWrap
                                display="block"
                              >
                                {app.candidate?.headline ||
                                  app.candidate?.email ||
                                  "—"}
                              </Typography>
                            </Box>
                          </Stack>
                        </TableCell>

                        {/* Job Applied Column */}
                        <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>
                          <Typography
                            variant="body2"
                            fontWeight={500}
                            color="text.primary"
                            sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 220 }}
                            title={app.job?.title || "Job"}
                          >
                            {app.job?.title || "Job"}
                          </Typography>
                          {app.job?.location && (
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              {app.job.location} · {app.job.employmentType}
                            </Typography>
                          )}
                        </TableCell>

                        {/* Match Score Column */}
                        <TableCell>
                          <MatchReport
                            matchResult={app.match}
                            variant="compact"
                          />
                        </TableCell>

                        {/* Status Column */}
                        <TableCell>
                          <StatusChip status={app.status} />
                        </TableCell>

                        {/* Submitted Date */}
                        <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>
                          <Typography variant="body2" color="text.secondary">
                            {new Date(app.submittedAt).toLocaleDateString(
                              "en-GB",
                              {
                                day: "2-digit",
                                month: "short",
                                year: "numeric",
                              },
                            )}
                          </Typography>
                        </TableCell>

                        {/* Actions */}
                        <TableCell align="right">
                          <Stack
                            direction="row"
                            spacing={0.5}
                            justifyContent="flex-end"
                            alignItems="center"
                          >
                            <Tooltip title="Review full application">
                              <Button
                                component={RouterLink}
                                to={`/employer/jobs/${app.jobId}/applicants/${app.id}`}
                                size="small"
                                variant="outlined"
                                sx={{
                                  py: 0.25,
                                  px: 1.25,
                                  fontSize: "0.8125rem",
                                }}
                              >
                                Review
                              </Button>
                            </Tooltip>

                            <Tooltip title="Update status">
                              <IconButton
                                size="small"
                                onClick={() =>
                                  setStatusDialog({
                                    open: true,
                                    application: app,
                                  })
                                }
                                sx={{ color: "text.secondary" }}
                              >
                                <FilterListRounded fontSize="small" />
                              </IconButton>
                            </Tooltip>

                            <Tooltip title="Download candidate CV">
                              <span>
                                <IconButton
                                  size="small"
                                  onClick={() => handleDownloadCv(app)}
                                  disabled={downloadingId === app.id}
                                  sx={{ color: "text.secondary" }}
                                >
                                  {downloadingId === app.id ? (
                                    <CircularProgress size={16} />
                                  ) : (
                                    <DownloadRounded fontSize="small" />
                                  )}
                                </IconButton>
                              </span>
                            </Tooltip>
                          </Stack>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
            </Box>

            {/* Pagination Controls */}
            <TablePagination
              rowsPerPageOptions={[10, 25, 50]}
              component="div"
              count={filteredApplications.length}
              rowsPerPage={pageSize}
              page={page}
              onPageChange={(_: unknown, newPage: number) => setPage(newPage)}
              onRowsPerPageChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(0);
              }}
              sx={{ borderTop: `1px solid ${neutral[200]}` }}
            />
          </>
        )}
      </Card>

      {/* Status Update Modal */}
      {statusDialog.open && statusDialog.application && (
        <StatusUpdateDialog
          open={statusDialog.open}
          onClose={() => setStatusDialog({ open: false, application: null })}
          application={statusDialog.application}
          onStatusChange={handleStatusChange}
          loading={updatingStatus}
        />
      )}
    </PageLayout>
  );
}
