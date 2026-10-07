import { getErrorMessage } from "@/api/errors";
import * as jobsApi from "@/api/jobs";
import { getSkills } from "@/api/skills";
import { FormSelect, FormTextField } from "@/components/shared/forms";
import { useToast } from "@/hooks/useToast";
import {
  jobFormSchema,
  toJobFormValues,
  toJobPayload,
  type JobFormValues,
} from "@/schemas/job";
import { EMPLOYMENT_TYPES, type Job } from "@/types/jobs";
import { todayAsInputValue } from "@/utils/dates";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  CircularProgress,
  MenuItem,
  Stack,
  TextField,
} from "@mui/material";
import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";

interface JobFormProps {
  mode: "create" | "edit";
  job?: Job;
  onSaved: (job: Job) => void;
  onCancel: () => void;
}

export default function JobForm({
  mode,
  job,
  onSaved,
  onCancel,
}: JobFormProps) {
  const toast = useToast();
  const {
    control,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<JobFormValues>({
    resolver: zodResolver(jobFormSchema),
    defaultValues: job ? toJobFormValues(job) : { requiredSkills: [], deadline: '' },
  });
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [availableSkills, setAvailableSkills] = useState<string[]>([]);

  useEffect(() => {
    getSkills()
      .then((skills) => setAvailableSkills(skills.map((s) => s.name)))
      .catch(console.error);
  }, []);

  async function onSubmit(values: JobFormValues) {
    setSubmitError(null);
    try {
      const payload = toJobPayload(values);
      const saved =
        mode === "edit" && job
          ? await jobsApi.updateJob(job.id, payload)
          : await jobsApi.createJob(payload);
      toast.success(
        mode === "edit"
          ? "Job updated successfully!"
          : "Job posted successfully!",
      );
      onSaved(saved);
    } catch (err) {
      setSubmitError(getErrorMessage(err));
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      <Stack spacing={2.5}>
        {submitError && <Alert severity="error">{submitError}</Alert>}
        <FormTextField<JobFormValues>
          name="title"
          control={control}
          label="Job title"
          autoFocus
        />
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
          <Box sx={{ flex: 1 }}>
            <FormTextField<JobFormValues>
              name="location"
              control={control}
              label="Location"
            />
          </Box>
          <Box sx={{ flex: 1 }}>
            <FormSelect<JobFormValues>
              name="employmentType"
              control={control}
              label="Employment type"
            >
              {EMPLOYMENT_TYPES.map((type) => (
                <MenuItem
                  key={type}
                  value={type}
                  sx={{ textTransform: "capitalize" }}
                >
                  {type.replace("-", " ")}
                </MenuItem>
              ))}
            </FormSelect>
          </Box>
        </Stack>
        <Controller
          name="requiredSkills"
          control={control}
          render={({ field, fieldState: { error } }) => (
            <Autocomplete
              multiple
              freeSolo
              options={availableSkills}
              value={field.value || []}
              onChange={(_, newValue) => {
                field.onChange(newValue);
              }}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Required skills"
                  placeholder="e.g. Python, MongoDB, Docker"
                  error={!!error}
                  helperText={error?.message}
                />
              )}
            />
          )}
        />
        <FormTextField<JobFormValues>
          name="deadline"
          control={control}
          label="Applications close on"
          type="date"
          slotProps={{
            inputLabel: { shrink: true },
            // Mirrors the schema's own rule, so the browser greys out the dates
            // the server would reject instead of offering them and then failing.
            htmlInput: { min: todayAsInputValue() },
          }}
          helperText="Optional. The role closes to new applications at the end of this day."
        />
        <FormTextField<JobFormValues>
          name="description"
          control={control}
          label="Description"
          multiline
          minRows={5}
        />
        <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end" }}>
          <Button onClick={onCancel} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={isSubmitting}
            startIcon={
              isSubmitting ? (
                <CircularProgress size={18} color="inherit" />
              ) : undefined
            }
          >
            {isSubmitting
              ? "Saving…"
              : mode === "edit"
                ? "Save changes"
                : "Post job"}
          </Button>
        </Stack>
      </Stack>
    </form>
  );
}
