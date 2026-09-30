# Design specification

The workspace uses a warm ivory canvas, deep forest accents, serif editorial headings and small, legible evidence labels. A slim navigation rail lists research sessions; the central conversation introduces the archive with suggested prompts and a bottom composer. The collapsible right pane displays a writing artifact with preview/source tabs and download.

## States
Startup: load recent sessions and health independently; show a diagnostic banner if dependencies are unavailable. Empty: show suggested questions, no fake messages or metrics. Retrieving: disable duplicate submission and announce progress. Streaming: display provisional tokens and evidence cards. Complete: replace provisional text with the validated persisted message and open any artifact. Failure: show a useful error and restore the question for retry. Session changes are disabled during generation.

## Interaction
Provider select switches local Ollama / cloud Anthropic; disable cloud unless a key is configured. Mode select chooses cited answer / Ship 30 essay / HTML brief. Each evidence card exposes guest, episode, timestamp, similarity and full excerpt, with an external original-source link. Artifact controls provide preview, source, download and close. Essay word count is shown as an observed value, not a guaranteed length.

## Responsive and accessible behavior
At desktop widths use navigation + conversation + artifact. Below 1100px hide the rail and provide a session dropdown. Below 850px place the artifact beneath the conversation. Keyboard-visible focus, labeled controls, semantic forms, disabled busy actions, an aria-live status and reduced-motion support are required. Enter submits; Shift+Enter adds a line. Render text through React/Markdown rather than dangerous innerHTML. HTML artifact preview is the sole iframe surface.
