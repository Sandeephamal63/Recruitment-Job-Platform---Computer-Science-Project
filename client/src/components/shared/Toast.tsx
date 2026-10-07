import {
  CheckCircleRounded,
  CloseRounded,
  ErrorRounded,
  InfoRounded,
  WarningAmberRounded,
} from "@mui/icons-material";
import { Box, IconButton, Stack, Typography, keyframes } from "@mui/material";
import { type CustomContentProps, useSnackbar } from "notistack";
import React, { forwardRef } from "react";

const toastProgress = keyframes`
  from {
    width: 100%;
  }
  to {
    width: 0%;
  }
`;

const toastEntrance = keyframes`
  0% {
    opacity: 0;
    transform: translateY(12px) scale(0.96);
  }
  60% {
    transform: translateY(-2px) scale(1.01);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
`;

interface VariantVisual {
  icon: React.ElementType;
  accentColor: string;
  lightBg: string;
  borderColor: string;
  iconBg: string;
  defaultTitle: string;
  badgeLabel: string;
}

const VARIANT_CONFIG: Record<string, VariantVisual> = {
  success: {
    icon: CheckCircleRounded,
    accentColor: "#2F7D4F",
    lightBg: "#FFFFFF",
    borderColor: "#C6E7D2",
    iconBg: "#EAF6EE",
    defaultTitle: "Success",
    badgeLabel: "Completed",
  },
  error: {
    icon: ErrorRounded,
    accentColor: "#B42318",
    lightBg: "#FFFFFF",
    borderColor: "#FECDCA",
    iconBg: "#FEF3F2",
    defaultTitle: "Error occurred",
    badgeLabel: "Action required",
  },
  warning: {
    icon: WarningAmberRounded,
    accentColor: "#B4740C",
    lightBg: "#FFFFFF",
    borderColor: "#FEDF89",
    iconBg: "#FFFAEB",
    defaultTitle: "Attention needed",
    badgeLabel: "Notice",
  },
  info: {
    icon: InfoRounded,
    accentColor: "#414639",
    lightBg: "#FFFFFF",
    borderColor: "#E4E6DB",
    iconBg: "#F1F2EA",
    defaultTitle: "Information",
    badgeLabel: "Update",
  },
  default: {
    icon: InfoRounded,
    accentColor: "#8A3413",
    lightBg: "#FFFFFF",
    borderColor: "#E4E6DB",
    iconBg: "#F6F1E6",
    defaultTitle: "Notification",
    badgeLabel: "Notice",
  },
};

const DEFAULT_DURATION_MS = 4500;

const Toast = forwardRef<HTMLDivElement, CustomContentProps>(function Toast(
  { id, message, variant, action },
  ref,
) {
  const { closeSnackbar } = useSnackbar();

  const config =
    VARIANT_CONFIG[variant as keyof typeof VARIANT_CONFIG] ??
    VARIANT_CONFIG.default;
  const Icon = config.icon;

  // Extract title and body if newline-separated, or use default title
  let title = config.defaultTitle;
  let body: React.ReactNode = message;

  if (typeof message === "string") {
    const parts = message.split("\n");
    if (parts.length > 1) {
      title = parts[0];
      body = parts.slice(1).join("\n");
    } else {
      // If single line, keep title as default or capitalize contextually
      body = parts[0];
    }
  }

  const actionContent = typeof action === "function" ? action(id) : action;

  return (
    <Box
      ref={ref}
      role="alert"
      aria-live="polite"
      sx={{
        width: { xs: "calc(100vw - 32px)", sm: 380 },
        maxWidth: 420,
        position: "relative",
        borderRadius: "12px",
        overflow: "hidden",
        backgroundColor: config.lightBg,
        border: `1px solid ${config.borderColor}`,
        boxShadow:
          "0 4px 6px -1px rgba(22, 26, 18, 0.06), 0 12px 24px -4px rgba(22, 26, 18, 0.12)",
        animation: `${toastEntrance} 0.32s cubic-bezier(0.16, 1, 0.3, 1)`,
        transition: "transform 0.2s ease, box-shadow 0.2s ease",
        cursor: "default",
        userSelect: "none",
        "&:hover": {
          transform: "translateY(-2px)",
          boxShadow:
            "0 8px 12px -2px rgba(22, 26, 18, 0.08), 0 18px 32px -6px rgba(22, 26, 18, 0.16)",
        },
        "&:hover .toast-progress-bar": {
          animationPlayState: "paused",
        },
      }}
    >
      {/* Visual Accent Left Strip */}
      <Box
        sx={{
          position: "absolute",
          top: 0,
          left: 0,
          width: 5,
          height: "100%",
          backgroundColor: config.accentColor,
        }}
      />

      <Box sx={{ pl: 2.5, pr: 1.5, py: 1.75 }}>
        <Stack direction="row" spacing={1.5} alignItems="flex-start">
          {/* Icon Badge */}
          <Box
            sx={{
              width: 36,
              height: 36,
              borderRadius: "10px",
              backgroundColor: config.iconBg,
              border: `1px solid ${config.borderColor}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
              mt: 0.25,
            }}
          >
            <Icon sx={{ fontSize: 20, color: config.accentColor }} />
          </Box>

          {/* Text Content */}
          <Box sx={{ flex: 1, minWidth: 0, pt: 0.2 }}>
            <Stack
              direction="row"
              alignItems="center"
              spacing={1}
              sx={{ mb: 0.35 }}
            >
              <Typography
                variant="subtitle2"
                sx={{
                  fontWeight: 700,
                  fontSize: "0.875rem",
                  color: "#161A12",
                  letterSpacing: "-0.01em",
                  lineHeight: 1.25,
                }}
              >
                {title}
              </Typography>
              <Box
                component="span"
                sx={{
                  fontSize: "0.6875rem",
                  fontWeight: 600,
                  px: 0.75,
                  py: 0.15,
                  borderRadius: "999px",
                  backgroundColor: config.iconBg,
                  color: config.accentColor,
                  border: `1px solid ${config.borderColor}`,
                  display: { xs: "none", sm: "inline-block" },
                }}
              >
                {config.badgeLabel}
              </Box>
            </Stack>

            {body && (
              <Typography
                variant="body2"
                sx={{
                  fontSize: "0.8125rem",
                  color: "#5C6252",
                  lineHeight: 1.45,
                  fontWeight: 450,
                  wordBreak: "break-word",
                }}
              >
                {body}
              </Typography>
            )}

            {/* Interactive Action Node if present */}
            {actionContent && (
              <Box sx={{ mt: 1.25, display: "flex", gap: 1 }}>
                {actionContent}
              </Box>
            )}
          </Box>

          {/* Close Action */}
          <IconButton
            size="small"
            onClick={() => closeSnackbar(id)}
            aria-label="Dismiss notification"
            sx={{
              color: "#A9AE9C",
              width: 28,
              height: 28,
              borderRadius: "6px",
              mt: -0.25,
              mr: -0.5,
              flexShrink: 0,
              transition: "all 0.15s ease",
              "&:hover": {
                color: "#161A12",
                backgroundColor: "#F1F2EA",
              },
            }}
          >
            <CloseRounded sx={{ fontSize: 16 }} />
          </IconButton>
        </Stack>
      </Box>

      {/* Interactive Pause-on-Hover Progress Bar */}
      <Box
        className="toast-progress-bar"
        sx={{
          position: "absolute",
          bottom: 0,
          left: 0,
          height: 3,
          backgroundColor: config.accentColor,
          opacity: 0.7,
          animation: `${toastProgress} ${DEFAULT_DURATION_MS}ms linear forwards`,
        }}
      />
    </Box>
  );
});

export default Toast;
