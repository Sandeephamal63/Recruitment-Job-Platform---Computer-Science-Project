import {
  DeleteOutlined,
  DescriptionOutlined,
  DriveFileMoveOutlined,
  ErrorOutlined,
  PictureAsPdfOutlined,
} from "@mui/icons-material";
import {
  Alert,
  Box,
  Card,
  Divider,
  IconButton,
  LinearProgress,
  Typography,
} from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import { useCallback, useRef, useState } from "react";

export interface DropzoneAcceptConfig {
  types: string[];
  maxSize?: number;
}

export interface DropzoneProps {
  accept?: DropzoneAcceptConfig;
  onFileSelect: (file: File) => void;
  busy?: boolean;
  progress?: number;
  error?: string | null;
  onErrorDismiss?: () => void;
  helperText?: string;
  disabled?: boolean;
  existingFileName?: string | null;
  existingFileSize?: number | null;
  existingFileUrl?: string | null;
  onRemoveExisting?: () => void;
  onDownload?: () => void;
  uploadLabel?: string;
  getFileIcon?: (type: string) => React.ReactNode;
  compact?: boolean;
  className?: string;
}

const FILE_TYPE_ICONS: Record<string, React.ReactNode> = {
  "application/pdf": <PictureAsPdfOutlined fontSize="large" color="error" />,
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
    <DescriptionOutlined fontSize="large" color="primary" />
  ),
  "image/png": <DescriptionOutlined fontSize="large" color="success" />,
  "image/jpeg": <DescriptionOutlined fontSize="large" color="success" />,
  "image/svg+xml": <DescriptionOutlined fontSize="large" color="info" />,
};

function getFileTypeIcon(type: string): React.ReactNode {
  return FILE_TYPE_ICONS[type] ?? <DescriptionOutlined fontSize="large" color="disabled" />;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

const DEFAULT_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];
const DEFAULT_MAX_SIZE = 5 * 1024 * 1024;

export function Dropzone({
  accept = { types: DEFAULT_TYPES, maxSize: DEFAULT_MAX_SIZE },
  onFileSelect,
  busy = false,
  progress,
  error,
  onErrorDismiss,
  helperText,
  disabled = false,
  existingFileName = null,
  existingFileSize = null,
  existingFileUrl: _existingFileUrl = null,
  onRemoveExisting,
  onDownload: _onDownload,
  uploadLabel = "Upload file",
  getFileIcon: _getFileIcon,
  compact = false,
  className,
}: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const theme = useTheme();

  const acceptTypes = accept.types ?? DEFAULT_TYPES;
  const maxSize = accept.maxSize ?? DEFAULT_MAX_SIZE;

  const validateFile = useCallback(
    (file: File): string | null => {
      if (acceptTypes.length && !acceptTypes.includes(file.type)) {
        const labels = acceptTypes
          .map((t) => t.split("/")[1]?.toUpperCase() ?? t)
          .join(", ");
        return `Unsupported file type. Accepted: ${labels}.`;
      }
      if (file.size > maxSize) {
        return `File too large. Maximum size is ${Math.round(maxSize / 1024 / 1024)} MB.`;
      }
      return null;
    },
    [acceptTypes, maxSize],
  );

  const handleFile = useCallback(
    (file: File) => {
      const err = validateFile(file);
      if (err) {
        setValidationError(err);
        return;
      }
      setValidationError(null);
      onFileSelect(file);
    },
    [onFileSelect, validateFile],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      if (disabled || busy) return;
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [disabled, busy, handleFile],
  );

  const onDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!disabled && !busy) setDragActive(true);
    },
    [disabled, busy],
  );

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
  }, []);

  const onChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (!e.currentTarget.files?.length) return;
      handleFile(e.currentTarget.files[0]);
      e.currentTarget.value = "";
    },
    [handleFile],
  );

  const openFilePicker = useCallback(() => {
    if (!disabled && !busy) inputRef.current?.click();
  }, [disabled, busy]);

  const acceptedTypesText = acceptTypes
    .map((t) => `.${t.split("/")[1] ?? t}`)
    .join(", ");

  const maxSizeText = `Max ${Math.round(maxSize / 1024 / 1024)} MB`;

  const displayedError = validationError ?? error ?? null;

  const errorSection = displayedError ? (
    <Alert
      severity="error"
      variant="outlined"
      onClose={() => {
        setValidationError(null);
        if (!validationError) onErrorDismiss?.();
      }}
      sx={{ mb: 2, borderRadius: 2 }}
      icon={<ErrorOutlined fontSize="small" />}
    >
      {displayedError}
    </Alert>
  ) : null;

  const filePreviewSection =
    existingFileName && !displayedError ? (
      <Card
        sx={{
          mb: 2,
          p: 2,
          borderRadius: 2,
          border: "1px solid",
          borderColor: "success.main",
          bgcolor: (t) => alpha(t.palette.success.main, 0.06),
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 1.5,
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, flex: 1, minWidth: 0 }}>
          <Box
            sx={{
              width: 48,
              height: 48,
              borderRadius: 2,
              bgcolor: (t) => alpha(t.palette.primary.main, 0.1),
              color: "primary.main",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            {getFileTypeIcon(acceptTypes[0])}
          </Box>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="body1" fontWeight={500} noWrap color="text.primary">
              {existingFileName}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {existingFileSize
                ? `${formatFileSize(existingFileSize)} • Uploaded`
                : "Uploaded"}
            </Typography>
          </Box>
        </Box>

        {onRemoveExisting && (
          <IconButton
            size="small"
            color="error"
            onClick={onRemoveExisting}
            disabled={busy}
            aria-label="Remove selected file"
            sx={{
              width: 36,
              height: 36,
              flexShrink: 0,
              border: `1px solid ${theme.palette.divider}`,
              "&:hover": { bgcolor: "error.main", color: "white", borderColor: "error.main" },
            }}
          >
            <DeleteOutlined fontSize="small" />
          </IconButton>
        )}
      </Card>
    ) : null;

  const uploadContent = existingFileName ? (
    <Box>
      <Typography variant="caption" color="text.secondary" gutterBottom>
        Drag a new file or click to replace
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {acceptedTypesText} • {maxSizeText}
      </Typography>
    </Box>
  ) : (
    <Box>
      <Box
        sx={{
          width: 64,
          height: 64,
          borderRadius: "50%",
          bgcolor: dragActive
            ? "primary.main"
            : (t) => alpha(t.palette.primary.main, 0.1),
          color: dragActive ? "common.white" : "primary.main",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          mx: "auto",
          mb: 2,
          transition: "all 0.18s cubic-bezier(0.34, 1.56, 0.64, 1)",
          transform: dragActive ? "scale(1.1)" : "scale(1)",
          boxShadow: dragActive
            ? `0 8px 24px ${alpha(theme.palette.primary.main, 0.3)}`
            : "none",
        }}
      >
        <DriveFileMoveOutlined sx={{ fontSize: 32 }} />
      </Box>

      <Typography variant="h6" fontWeight={600} gutterBottom>
        {uploadLabel}
      </Typography>

      {helperText && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {helperText}
        </Typography>
      )}

      <Typography variant="caption" color="text.secondary">
        {acceptedTypesText} • {maxSizeText}
      </Typography>
    </Box>
  );

  const progressSection = busy ? (
    <Box sx={{ mt: 3, display: "flex", flexDirection: "column", alignItems: "center", gap: 1 }}>
      <LinearProgress
        variant={progress !== undefined ? "determinate" : "indeterminate"}
        value={progress}
        sx={{ width: "100%", maxWidth: 300, height: 6, borderRadius: 3 }}
      />
      <Typography variant="body2" color="text.secondary">
        {progress !== undefined ? `Uploading... ${Math.round(progress)}%` : "Uploading..."}
      </Typography>
    </Box>
  ) : null;

  return (
    <Box sx={{ width: "100%" }} className={className}>
      {errorSection}
      {filePreviewSection}

      {filePreviewSection && <Divider sx={{ mb: 2 }} />}

      <Box
        role="button"
        tabIndex={disabled || busy ? -1 : 0}
        aria-label={uploadLabel}
        aria-disabled={disabled || busy}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={openFilePicker}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            openFilePicker();
          }
        }}
        sx={{
          border: "2px dashed",
          borderColor: dragActive
            ? "primary.main"
            : displayedError
              ? "error.main"
              : "divider",
          borderRadius: 2,
          p: compact ? 2 : { xs: 3, sm: 4 },
          textAlign: "center",
          cursor: disabled || busy ? "not-allowed" : "pointer",
          outline: "none",
          transition: "border-color 0.16s ease, background-color 0.16s ease, box-shadow 0.16s ease",
          bgcolor: dragActive
            ? (t) => alpha(t.palette.primary.main, 0.05)
            : "transparent",
          boxShadow: dragActive
            ? (t) => `0 0 0 3px ${alpha(t.palette.primary.main, 0.15)}`
            : "none",
          "&:hover": {
            borderColor: disabled || busy ? "divider" : "primary.main",
            bgcolor: disabled || busy
              ? "transparent"
              : (t) => alpha(t.palette.primary.main, 0.03),
          },
          "&:focus-visible": {
            borderColor: "primary.main",
            boxShadow: (t) => `0 0 0 3px ${alpha(t.palette.primary.main, 0.25)}`,
          },
          opacity: disabled ? 0.6 : 1,
        }}
      >
        <input
          ref={inputRef}
          type="file"
          hidden
          accept={acceptTypes.join(",")}
          onChange={onChange}
          disabled={disabled || busy}
          tabIndex={-1}
          aria-hidden="true"
        />
        {uploadContent}
        {progressSection}
      </Box>
    </Box>
  );
}

export default Dropzone;
