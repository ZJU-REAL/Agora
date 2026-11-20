---
name: Agora Studio
description: Illustrated social-world workbench for the Developer and Viewer outer framework.
colors:
  ink: "#2c3352"
  body: "#4a536f"
  muted: "#5b6680"
  line: "#e2e7f2"
  paper: "#fff"
  canvas: "#fafbff"
  stone: "#f0f3fc"
  accent: "#5264b6"
  blue: "#4058b7"
  green: "#2b7865"
  button-hover: "#424b75"
  secondary-hover: "#e8edfa"
  navigation-hover: "#e8edf8"
  mode-selected: "#3d486f"
  sidebar-selected: "#e9efff"
  sidebar-selected-ink: "#4059a4"
  field-line: "#dce2ef"
  summary-divider: "#dbe2f1"
  row-selected: "#e5ecff"
  playback-surface: "#eef2ff"
  playback-action: "#42507d"
  dialog-surface: "#fcfdff"
  success-surface: "#e6f2e9"
  success-text: "#256848"
  error-surface: "#ffedf0"
  error-text: "#a72e3a"
  paused-surface: "#fff0d9"
  paused-text: "#825108"
  role-surface: "#ffead1"
  platform-selected: "#f3f5ff"
  platform-hover-line: "#9da9ce"
  field-hover-line: "#a7b3d1"
  avatar-surface: "#e5eafa"
  selection-lavender: "#e5dcff"
typography:
  display:
    fontFamily: '"Agora Display", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 28px
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: -0.025em
  headline:
    fontFamily: '"Agora Display", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 23px
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: -0.025em
  title:
    fontFamily: '"Agora Display", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.4
  summary-title:
    fontFamily: '"Agora Display", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 19px
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: '"Agora Text", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
  supporting:
    fontFamily: '"Agora Text", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.7
  rationale:
    fontFamily: '"Agora Text", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.8
  label:
    fontFamily: '"Agora Text", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 12px
    fontWeight: 500
    lineHeight: 1.5
  action:
    fontFamily: '"Agora Text", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.5
  navigation:
    fontFamily: '"Agora Text", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.5
  metadata:
    fontFamily: '"Agora Text", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 11px
    fontWeight: 400
    lineHeight: 1.5
  code:
    fontFamily: ui-monospace, SFMono-Regular, Consolas, monospace
    fontSize: 10px
    fontWeight: 400
    lineHeight: 1.7
  mobile-control:
    fontFamily: '"Agora Text", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.5
rounded:
  badge: 5px
  status: 6px
  replay-control: 7px
  inset: 8px
  field: 9px
  control: 10px
  platform: 11px
  surface: 12px
  dialog: 16px
  circle: 50%
spacing:
  "3": 3px
  "4": 4px
  "5": 5px
  "6": 6px
  "7": 7px
  "8": 8px
  "9": 9px
  "10": 10px
  "11": 11px
  "12": 12px
  "14": 14px
  "15": 15px
  "16": 16px
  "18": 18px
  "20": 20px
  "22": 22px
  "24": 24px
  "28": 28px
  "32": 32px
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    typography: "{typography.action}"
    rounded: "{rounded.control}"
    padding: 9px 15px
  button-primary-hover:
    backgroundColor: "{colors.button-hover}"
  button-secondary:
    backgroundColor: "{colors.stone}"
    textColor: "{colors.ink}"
    typography: "{typography.action}"
    rounded: "{rounded.control}"
    padding: 9px 15px
  button-secondary-hover:
    backgroundColor: "{colors.secondary-hover}"
  button-text:
    backgroundColor: transparent
    textColor: "{colors.accent}"
    typography: "{typography.label}"
    padding: 6px 0
  button-text-hover:
    textColor: "{colors.ink}"
  input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: 9px 11px
    width: 100%
  mode-navigation:
    backgroundColor: "{colors.stone}"
    rounded: "{rounded.surface}"
    padding: 4px
  mode-navigation-active:
    backgroundColor: "{colors.mode-selected}"
    textColor: "{colors.paper}"
    typography: "{typography.navigation}"
    rounded: "{rounded.field}"
    padding: 7px 14px
  status:
    backgroundColor: "{colors.stone}"
    textColor: "{colors.body}"
    typography: "{typography.metadata}"
    rounded: "{rounded.status}"
    padding: 5px 7px
  status-success:
    backgroundColor: "{colors.success-surface}"
    textColor: "{colors.success-text}"
  status-error:
    backgroundColor: "{colors.error-surface}"
    textColor: "{colors.error-text}"
  status-paused:
    backgroundColor: "{colors.paused-surface}"
    textColor: "{colors.paused-text}"
  configuration-form:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
  configuration-section:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    padding: 22px 24px
  platform-choice:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.body}"
    rounded: "{rounded.platform}"
    padding: 15px 12px
  platform-choice-selected:
    backgroundColor: "{colors.platform-selected}"
    textColor: "{colors.ink}"
    rounded: "{rounded.platform}"
    padding: 14px 11px
  actor-card:
    backgroundColor: transparent
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: 11px 9px
    width: 100%
  actor-card-selected:
    backgroundColor: "{colors.row-selected}"
  playback:
    backgroundColor: "{colors.playback-surface}"
    rounded: "{rounded.control}"
    padding: 8px 10px
  run-summary:
    backgroundColor: "{colors.stone}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
    padding: 20px
  brand-wordmark:
    width: 144px
    height: 57px
  model-dialog:
    backgroundColor: "{colors.dialog-surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.dialog}"
    padding: "0"
    width: min(760px, calc(100vw - 32px))
---

# Design System: Agora Studio

## Overview

**Creative North Star: "The Illustrated Social Workbench"**

Agora Studio is a compact social-world workbench with the approved illustrated, anime-influenced identity. The user-supplied Agora wordmark and world illustration establish the personality: cool indigo drawing, blue and lavender planes, and small pink, peach and golden details. Near-white working surfaces, modest headings and tightly grouped controls give configuration and observation the main share of the screen.

This design system applies to the Developer and Viewer outer framework in `agora/web/studio.html`, `studio.css` and `studio.js`. Xiaohongshu, X/Twitter and Reddit iframe documents retain their native typography, color, layout and interaction. Branding provides orientation; account actions, observations, counts and public rationales remain actual recorded interface content.

**Key Characteristics:**

- Official illustrated wordmark and world artwork, reused proportionally without repainting.
- Near-white canvas, indigo ink, fine cool dividers and periwinkle selection states.
- Compact, divided work surfaces with self-hosted Latin fonts and system Chinese fallbacks.
- Platform-first configuration and a Viewer stage that receives the largest working column.
- Explicit status, keyboard focus, independently remembered account positions and short state transitions.
- Independent native social-platform styling inside each iframe.

The frontmatter records the final source values; prose explains their application. `.impeccable/design.json` extends these tokens with source-derived component previews, motion, breakpoints and the dialog shadow. Its synthesized tonal ramps are preview aids, not a shipped color scale. This merge preserves valid source tokens and the approved identity while replacing descriptions of earlier layouts. The surface strategy remains in `.impeccable/surfaces/agora-web-studio-html.md`; `docs/design.md` is the separate architecture document.

## Colors

Indigo text and blue-purple selection anchor a near-white workspace. The illustration retains its small pink, peach and gold details; the implemented platform choices use white resting surfaces and a shared periwinkle selected surface. Keep the incumbent source names, including `stone`, whose value is a cool grouping fill.

### Primary

- **Indigo Ink:** `ink` carries default text, headings, primary actions and the replay range. `button-hover` supplies the primary action hover fill. `mode-selected` is the darker active mode fill; `playback-action` fills the replay play control.
- **Periwinkle Accent:** `accent` carries text actions, explanatory icons, focused field borders and selected platform borders/checks. `blue` supplies the keyboard focus outline.

### Secondary

- **Cool Grouping Surface:** `stone` groups the run summary, secondary controls, mode navigation and small neutral badges. `secondary-hover` and `navigation-hover` preserve distinct hover feedback.
- **Selected Row Blue:** `row-selected` marks the selected account and historical timeline action. `sidebar-selected` and `sidebar-selected-ink` identify the current Developer section.
- **Selected Platform Periwinkle:** `platform-selected` sits beneath the selected platform's indigo edge and check. `platform-hover-line` strengthens the unselected hover edge.
- **Replay Blue:** `playback-surface` keeps the replay controls visible above the native viewport; the play control uses its own darker action fill.

### Tertiary

- **Functional Green:** `green` marks connection readiness and recorded successful outcomes. Success, error and paused token pairs supply explicit run-state chips and outcome treatments.
- **Warm Role Marker:** `role-surface` and `paused-text` identify the small “受测” badge. This cue marks account role, not simulation success.
- **Native Platform Identifiers:** Xiaohongshu red, X black and Reddit orange remain small identity marks within the platform choices. Their own styling stays in the platform documents and does not become an alternative studio action palette.

### Neutral

- **Cloud Canvas and White Paper:** `canvas` is the outer document; `paper` supports the masthead, configuration form, ordinary fields, decision panel and viewport. `dialog-surface` is the transient model dialog.
- **Indigo Gray Copy:** `body` carries secondary control copy and labels; `muted` supplies descriptions, metadata and window chrome. Keep these source roles distinct.
- **Fine Cool Lines:** `line` defines structural outlines and dividers, `field-line` outlines ordinary fields, `field-hover-line` supplies their hover edge, and `summary-divider` separates summary groups.
- **Avatar and Text Selection:** `avatar-surface` supplies the fallback initial avatar; `selection-lavender` is the browser text-selection fill.

**The Native Boundary Rule.** Apply these tokens to the outer framework only. Preserve the independent visual system inside each platform iframe.

## Typography

**Display Font:** Bricolage Grotesque, served locally as **Agora Display**, with PingFang SC, Microsoft YaHei and sans-serif fallbacks.

**Body Font:** Inter, served locally as **Agora Text**, followed by the system stack in the frontmatter. Chinese glyphs use the available system font.

**Code Font:** The source uses `ui-monospace, SFMono-Regular, Consolas, monospace` for parameter and result JSON. This is an explicit system fallback role, with no additional font download.

Rounded Latin headings continue the illustrated identity at practical workbench sizes. Body and controls stay direct and readable. The wordmark is an image; its lettering is not a reusable CSS text role.

### Hierarchy

- **Display:** `display` records the Developer title (28px, weight 700, leading 1.3). It becomes (23px) at the mobile breakpoint. Its bold weight follows the source heading's browser default; section titles explicitly use weight 600.
- **Headline:** `headline` records the Viewer run title (23px, weight 700, leading 1.4), becoming (19px) on mobile. It truncates to one line and retains the full run name in the title attribute.
- **Title:** `title` records section titles (18px, weight 600, leading 1.4). Mobile configuration titles use (16px). `summary-title` records the (19px) launch-summary title. The model-dialog title is (21px), becoming (19px) on mobile.
- **Body and Supporting:** `body` is the (14px) page baseline. Section descriptions use `supporting` (12px, leading 1.7). The Developer introduction is (13px), becoming (11px, leading 1.7, maximum 29ch) on mobile. Recorded public rationale uses `rationale` (12px, leading 1.8).
- **Labels and Actions:** `label` records field labels (12px, weight 500); `action` records primary and secondary controls (13px, weight 500). Mode links use `navigation` (13px, weight 400). Text actions are (12px, weight 500).
- **Metadata and Code:** `metadata` records ordinary secondary metadata (11px); dense Viewer details use (9–10px). `code` records the JSON details (10px, leading 1.7). Numeric counters, definition values and number inputs use tabular figures; the `mono` helper is a numeric treatment, not a monospace font declaration.

The source scale is functional rather than geometric. Display font weights are declared (400–700), body weights (400–600); both use `font-display: swap`, with font synthesis disabled. Preserve the self-hosted files, `licenses/console-fonts.json` and adjacent SIL OFL files. At the mobile breakpoint ordinary inputs, textareas and selects, Viewer selectors and replay speed use `mobile-control` (16px) text.

**The Readable Control Rule.** Preserve the mobile control text size (16px) so focusing a field does not trigger iPhone Safari zoom. Keep the replay-speed selector (56px) wide and prevent it from shrinking.

## Layout

Developer uses a (176px) sidebar and flexible main column within (1540px). The sticky masthead is (68px) high with (28px) side padding. Main padding is (24px 32px 0). Its compact heading has (94px) minimum height, (20px) bottom separation and a proportionally contained (108px by 96px) world image. The form and sticky summary use a (24px) gap with a (270px) summary column; the summary sits (24px) below the masthead.

The desktop configuration is one outlined white form divided into three sections, each with (22px 24px) padding. Platform choices stay in three equal columns with a (10px) gap. The focal/background account groups and ordinary field pairs use two columns with (16px) separation; the short run budget uses three columns. A fine vertical divider distinguishes model roles. The summary uses (20px) padding. Recent runs form a divided list beneath the configuration.

Viewer uses a maximum width of (1800px) with (22px 24px 16px) page padding. A compact heading and selectors precede a (170px / flexible / 300px) workspace with (18px) gaps. The account list is narrow, the native stage receives the largest column, and the current-action/record panel is bounded. Workspace height is `max(580px, calc(100dvh - 312px))`; the iframe flexes within its viewport after the stage heading, replay bar, (31px) chrome and context note. Lists and details scroll inside their available space; they do not force the full viewport taller.

Responsive behavior follows the final source breakpoints:

- **At (1500px) and wider:** Viewer side columns become (180px) and (320px), with (22px) gaps.
- **At (1199px) and narrower:** Developer sidebar becomes (150px), main padding (22px 22px 0), summary column (245px), layout gap (18px), and section padding (20px 18px). Platform descriptions hide while names and captions remain. Viewer uses (145px / flexible / 270px) columns, (14px) gaps and (20px 18px 16px) page padding. Expand text and the secondary replay-mode text hide; their controls and accessible names remain.
- **At (979px) and narrower:** Developer sidebar becomes a horizontal row below the masthead; the form retains a (255px) summary column. Viewer account selection becomes a full-width horizontal strip of (155px) cards. The stage and (285px) action panel sit below it; each has `max(560px, calc(100dvh - 390px))` height with a (580px) minimum. The account statistics/footer hide. Viewer selectors wrap.
- **At (699px) and narrower:** Header becomes (62px), wordmark (126px by 51px), and navigation keeps text while hiding icons. Developer uses (16px 14px 0) main padding, a (76px) minimum heading, (10px) bottom gap and (78px by 70px) illustration. Configuration sections become individual (12px) rounded surfaces with (18px 15px) padding. Visual order is platform, launch summary, account/model setup, run settings, then save controls; the summary is static with (12px) padding. Two account-role columns and three short budget fields remain. Summary values use two columns. There is no fixed mobile launch bar; the existing launch action stays in the visible summary after platform selection.
- **Mobile Viewer:** Page padding is (16px 12px); selectors and status/actions wrap. Account cards are (146px) wide and scroll horizontally. The stage is (650px) high, followed by the (590px) current-action/record panel. The latter divides bounded detail and scrolling records. Run controls move below the workspace. Replay stays on one compact row with (28px) step controls and a non-shrinking (56px) speed selector.

Expanded Viewer mode hides the account and action panels and gives the same stage the full width. Desktop expanded height is `calc(100dvh - 220px)` with a (580px) minimum; mobile uses `calc(100dvh - 255px)` with the same minimum. Expansion changes the outer layout and preserves iframe identity, account and step.

## Elevation & Depth

Working surfaces are flat. Fine outlines and dividers describe grouping; the cool summary plane and selected-row fills provide emphasis. Sticky chrome uses borders and stacking. Only the transient model dialog has an ambient shadow; the toast is an indigo feedback surface without a shadow.

### Shadow Vocabulary

- **Model dialog:** `0 12px 48px #2c335229`; the backdrop is `#2c33524d`.

**The Flat Working Surface Rule.** Use outlines, dividers and tonal grouping for working surfaces. Reserve the implemented shadow for the model dialog.

Buttons and links transition background, text and border colors over (180ms ease-out). The toast moves (10px) and fades over the same duration. There is no continuous decorative motion. The reduced-motion query cancels transitions and restores automatic scrolling.

## Shapes

The current form language uses small rounded rectangles, fine structural lines and circular avatars/checks. Ordinary fields, account rows and navigation items use `field`; actions and replay planes use `control`; configuration and platform viewport containers use `surface`; the dialog uses `dialog`. Platform choices use `platform`, and selected choices strengthen the edge from (1px) to (2px) while reducing padding by (1px) to preserve their geometry. Replay steps are rounded squares using `replay-control`, not circular pills. Small status, count and role treatments use compact radii.

Official branding preserves transparent edges and uses `object-fit: contain`. Keep its aspect ratio and detail. The present compact heading has one small world illustration; it has no surrounding hero plane, large illustration region or decorative star components.

## Components

### Branding

The masthead links the official `agora/web/agora-wordmark.webp` image to the Developer entry with an accessible Agora home name. Its rendered size is (144px by 57px), with the mobile size above. Developer heading and Viewer empty state use `agora/web/agora-world.webp`; the empty-state image is (170px by 150px), becoming (150px by 134px) on mobile. Decorative instances have empty alternative text and are hidden from assistive technology. `agora/web/agora-favicon.png` remains the favicon. `agora/web/agora-mark.png` remains a retained identity asset and is not a current sidebar component.

The user supplied `agora_icon.png` and `agora_text.png` as the official identity. Their derivatives crop transparent padding and resize proportionally without repainting. Original PNGs, derivative files, source hashes and transformation metadata in `licenses/agora-artwork.json` remain unchanged. Application assets resolve through the existing `/static/` deployment routing. Use the artwork for branding and orientation; do not present it as account data, simulation outcome or evidence of model capability.

### Buttons

Compact rectangular actions use `control`, (9px 15px) padding and (40px) minimum height. Primary actions pair `ink` and `paper`; secondary actions pair `stone` and `ink`. Text actions are transparent, use `accent`, and switch to `ink` with an underline on hover. Keyboard focus is a (2px) blue outline with (3px) offset. Disabled buttons use (0.5) opacity and a not-allowed cursor. Launch is full width with a (43px) minimum height, becoming (42px) on mobile; run controls are smaller secondary actions with (34px) minimum height.

### Inputs / Fields

White fields use `field-line`, `field` radius, (9px 11px) padding and (40px) minimum height. Hover uses `field-hover-line`; focus uses `accent` plus the shared blue keyboard outline. Mobile fields use (16px) text, (8px) padding and (38px) minimum height. Textareas resize vertically. The agent stepper is one bordered container with centered numeric input and (38px) square buttons, becoming (28px by 36px) buttons on mobile. Keep the explicit total-agent label and hint that the total includes one focal account.

### Navigation and retained context

The top navigation contains distinct Developer and Viewer links in a cool (12px) rounded group. Active mode uses `mode-selected` and white copy. Platform and the remembered Viewer run follow mode changes. Developer section navigation links configuration, records and model connection; it becomes a horizontal scrolling row at narrower widths.

“探索当前平台” lives beside platform selection and opens the selected native world in a new tab. Configuration drafts are kept separately for each platform. Saved configuration and old-run reuse restore the appropriate platform and settings; reuse retains recommendation parameters beyond the visible controls rather than silently dropping them. This behavior belongs to the outer workflow, while platform browsing remains native.

### Configuration and launch summary

One divided form groups platform, account/model roles, and run settings. Focal account/model and background count/strategy are visually distinct, with an explicit “1 个受测账号 + N 个背景账号” explanation. Run intent is optional. Advanced runtime and recommendation settings use native expandable details.

The summary updates the focal identity, background count, rounds, each account's action ceiling, both model roles and total action ceiling. Total budget is agent count × rounds × actions per round. Readiness is a written status with an icon; invalid parameters, unavailable credentials, excessive budget, incompatible recommendation quantities and occupied runtime capacity block launch with a concrete message. Current runtime defaults shown by the interface are one concurrent run, 32 active agents and 2400 actions. Reuse opens a new configuration for review rather than replacing the original run. Mobile places this summary directly after platform selection to keep the launch path early in the page.

### Chips and selected choices

Run status is a compact chip with a current-color dot and explicit text. Successful/running, failed/interrupted and paused/pausing states use their source color pairs. Color supplements the written state. The focal-role badge uses the small warm marker.

All three platform choices share the same white/periwinkle selection treatment and retain their small native marks, names and platform captions. Selected choices show an indigo edge/check and `aria-pressed`. Descriptions hide at compact desktop widths; captions remain and can wrap. Account and timeline selected fills use `row-selected`.

### Account selection, statistics and records

Account buttons combine a small circular avatar, one-line name, role and recorded action count, with `aria-pressed` tracking the selection. Each actor retains an independent replay position; switching actors restores that position instead of resetting every actor to the beginning. Saved Viewer context retains at most eight runs. Narrow lists scroll horizontally.

Behavior bars count the selected account's recorded trajectory by browsing, creation, interaction and relationship actions. The record filter includes all types, these categories, system/other, and execution failure; counts describe the actual visible records. Filtering keeps the account's timeline positions intact. Current detail shows the recorded action, elapsed time, execution result, observed screen and public rationale when present. Missing rationale or outcome receives an explicit absence message. Parameters/results remain optional expandable JSON using the code role.

### Exact replay and native viewport

Previous/play/next buttons, a native range, position counter, replay speed and latest-state control sit above the viewport. Active runs distinguish “跟随最新” from “历史回放”; finished runs use “最新步骤”. Keyboard names remain when compact layouts hide the secondary replay text. Loading/empty messages belong to the observed stage, and controls disable when there is no trajectory.

Selecting a historical action synchronizes that action, its outcome and the observer frame before presenting the step; the loading treatment prevents an old screen from appearing as the newly selected record. The window explicitly labels observation as read-only. Expansion exposes a pressed state and changes the surrounding grid without replacing the iframe or selected step. Xiaohongshu, X/Twitter and Reddit maintain their independent document styling.

### Model dialog and feedback

The modal dialog is explicitly named with `aria-labelledby`. It uses the dialog fill, (16px) radius, recorded overlay shadow and `min(760px, calc(100vw - 32px))` width, with viewport-bounded scrolling. The sticky title row and body each use (24px) padding, becoming (18px) on mobile. Mobile dialog width is `calc(100vw - 24px)`; field pairs stack while the three short budget fields remain three columns. Saved-model choices wrap and distinguish the selected connection. Model feedback, launch readiness, connection health and toast retain status semantics. The toast uses indigo and white copy with a brief fade/move transition.

## Do's and Don'ts

### Do:

- **Do** reuse the supplied Agora wordmark and world derivatives, preserving proportions, illustration detail and transparent edges.
- **Do** keep the near-white canvas, indigo text and cool selection surfaces as the framework baseline.
- **Do** preserve the compact configuration sections, distinct model roles, total action budget and visible launch validation.
- **Do** retain field labels, keyboard focus outlines, dialog naming, actor pressed states and written status.
- **Do** restore each account’s independent historical position and keep the same iframe when expanding the stage.
- **Do** synchronize the displayed action, outcome and observed platform frame before presenting a historical step.
- **Do** use short state transitions and respect reduced-motion preferences.

### Don't:

- **Don't** return to the rejected single warm-yellow treatment or earlier terracotta framework palette.
- **Don't** replace the official illustrated wordmark with a CSS logo, text-only approximation or generated mascot.
- **Don't** apply studio typography, palette or decorative artwork to native social-platform documents.
- **Don't** use illustration, sample-world fixtures or missing record fields as evidence of model capability or observed behavior.
- **Don't** add ambient shadows to every working surface or continuous floating, particle or looping animation.
- **Don't** let artwork overlap labels, platform choices, launch actions or replay controls at narrow widths.
