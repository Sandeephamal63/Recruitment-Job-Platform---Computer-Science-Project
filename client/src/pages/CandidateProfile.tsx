import { getErrorMessage } from "@/api/errors";
import * as profileApi from "@/api/profile";
import AvatarImage from "@/components/shared/AvatarImage";
import Dropzone from "@/components/shared/Dropzone";
import PageContainer from "@/components/shared/PageContainer";
import { useToast } from "@/hooks/useToast";
import type { User } from "@/types/profile";
import { SaveOutlined } from "@mui/icons-material";
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  Divider,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import Grid from "@mui/material/Grid2";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getSkills } from "@/api/skills";
import { AVATAR_ACCEPT } from "@/schemas/profile";

export default function CandidateProfile() {
  const toast = useToast()
  const [profile, setProfile] = useState<User | null>(null);
  const [availableSkills, setAvailableSkills] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [cvBusy, setCvBusy] = useState(false);
  const [avatarBusy, setAvatarBusy] = useState(false);
  const [avatarError, setAvatarError] = useState<string | null>(null);
  // Bumped after every avatar write to make AvatarImage re-read its bytes; its
  // cache deliberately remembers a "no photo" answer for the session.
  const [avatarEpoch, setAvatarEpoch] = useState(0);

  const loadProfile = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await profileApi.getProfile();
      setProfile(data);
      if (data.role === "candidate") {
        const skillsData = await getSkills();
        setAvailableSkills(skillsData.map(s => s.name));
      }
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const handleSave = async () => {
    if (!profile) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await profileApi.updateProfile({
        headline: profile.headline,
        skills: profile.skills,
      });
      setProfile(updated);
      toast.success('Profile saved successfully!');
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleCvDownload = async () => {
    if (!profile?.hasProfileCv) return;
    try {
      const blob = await profileApi.downloadProfileCv();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = profile.cvFileName || "cv.pdf";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  const handleCvDelete = async () => {
    if (!profile?.hasProfileCv) return;
    try {
      const updated = await profileApi.deleteProfileCv();
      setProfile(updated);
      toast.success('CV removed.');
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  const handleCvUpload = useCallback(async (file: File) => {
    setCvBusy(true);
    setError(null);
    try {
      await profileApi.uploadProfileCv(file);
      setProfile(await profileApi.getProfile());
      toast.success('CV uploaded successfully!');
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setCvBusy(false);
    }
  }, [toast]);

  const handleAvatarUpload = useCallback(async (file: File) => {
    setAvatarBusy(true);
    setAvatarError(null);
    try {
      await profileApi.uploadAvatar(file);
      setProfile(await profileApi.getProfile());
      setAvatarEpoch((n) => n + 1);
      toast.success('Profile photo uploaded!');
    } catch (err) {
      setAvatarError(getErrorMessage(err));
    } finally {
      setAvatarBusy(false);
    }
  }, [toast]);

  const handleAvatarDelete = useCallback(async () => {
    setAvatarBusy(true);
    setAvatarError(null);
    try {
      setProfile(await profileApi.deleteAvatar());
      setAvatarEpoch((n) => n + 1);
      toast.info('Profile photo removed.');
    } catch (err) {
      setAvatarError(getErrorMessage(err));
    } finally {
      setAvatarBusy(false);
    }
  }, [toast]);


  if (loading) {
    return (
      <PageContainer sx={{ py: 5 }}>
        <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
          <CircularProgress />
        </Box>
      </PageContainer>
    );
  }

  if (!profile) {
    return (
      <PageContainer sx={{ py: 5 }}>
        <Alert severity="error">Failed to load profile</Alert>
      </PageContainer>
    );
  }

  const isCandidate = profile.role === "candidate";

  return (
    <PageContainer sx={{ py: 3 }}>
      <Stack spacing={3}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            {isCandidate ? "Candidate Profile" : "Employer Profile"}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Manage your profile and CV
          </Typography>
        </Box>

        {error && (
          <Alert severity="error" onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Card variant="outlined" sx={{ p: 3 }}>
          <Stack
            direction="row"
            spacing={2}
            alignItems="center"
            sx={{ mb: 3, flexWrap: "wrap" }}
          >
            <AvatarImage ownAvatar epoch={avatarEpoch} name={profile.name} size={64} alt="" />
            <Stack>
              <Typography variant="h6">{profile.name}</Typography>
              <Typography variant="body2" color="text.secondary">
                {profile.email}
              </Typography>
              <Chip
                label={profile.role}
                size="small"
                color="primary"
                variant="outlined"
                sx={{ mt: 1 }}
              />
            </Stack>
          </Stack>

          <Divider sx={{ mb: 3 }} />

          <Grid container spacing={3}>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                fullWidth
                label="Headline"
                value={profile.headline || ""}
                onChange={(e) =>
                  setProfile({ ...profile, headline: e.target.value })
                }
                placeholder="e.g. Senior Frontend Engineer"
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <Autocomplete
                multiple
                freeSolo
                id="skills-autocomplete"
                options={availableSkills}
                value={profile.skills || []}
                onChange={(_, newValue) => {
                  setProfile({
                    ...profile,
                    skills: newValue as string[],
                  });
                }}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Skills"
                    placeholder="Add skills"
                  />
                )}
              />
            </Grid>
          </Grid>

          <Divider sx={{ my: 3 }} />

          <Typography variant="h6" gutterBottom>
            Profile photo
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Optional. Employers see this beside your name on their applicant list;
            without one they see your initials.
          </Typography>
          <Dropzone
            onFileSelect={handleAvatarUpload}
            busy={avatarBusy}
            error={avatarError}
            onErrorDismiss={() => setAvatarError(null)}
            helperText="PNG, JPEG or WEBP, max 1 MB"
            accept={AVATAR_ACCEPT}
            existingFileName={profile.avatarFileName ?? undefined}
            onRemoveExisting={profile.avatarFileName ? handleAvatarDelete : undefined}
            uploadLabel="Upload photo"
          />

          <Divider sx={{ my: 3 }} />

          <Typography variant="h6" gutterBottom>
            Profile CV
          </Typography>
          <Dropzone
            onFileSelect={handleCvUpload}
            busy={cvBusy}
            error={error || undefined}
            onErrorDismiss={() => setError(null)}
            helperText="PDF or DOCX, max 5 MB"
            existingFileName={profile.cvFileName ?? undefined}
            onRemoveExisting={profile.hasProfileCv ? handleCvDelete : undefined}
            onDownload={profile.hasProfileCv ? handleCvDownload : undefined}
            uploadLabel="Upload CV"
          />
        </Card>

        <Stack
          sx={{ mt: 3 }}
          direction="row"
          spacing={2}
          justifyContent="flex-end"
        >
          <Button component={Link} to="/dashboard">
            Back to Dashboard
          </Button>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={saving}
            startIcon={
              saving ? (
                <CircularProgress size={18} color="inherit" />
              ) : (
                <SaveOutlined />
              )
            }
          >
            Save Changes
          </Button>
        </Stack>
      </Stack>
    </PageContainer>
  );
}
