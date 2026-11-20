---
name: Agora Studio
description: Family-inspired visual system for the Developer and Viewer outer framework.
colors:
  ink: "#121212"
  body: "#474645"
  muted: "#66635f"
  line: "#e5e0d9"
  paper: "#fff"
  canvas: "#fbfaf9"
  stone: "#f2f0ed"
  accent: "#c93608"
  accent-soft: "#fff0e8"
  blue: "#006fcf"
  green: "#287553"
  brand-orange: "#ff3e00"
  selection-yellow: "#ffcd6c"
  button-hover: "#343433"
  secondary-hover: "#e8e4dd"
  navigation-hover: "#e8e4de"
  navigation-selected: "#eae6df"
  card-line: "#eeebe7"
  field-line: "#ddd8d0"
  field-focus: "#8c8378"
  selected-supporting: "#d5d0c8"
  success-surface: "#e6f2e9"
  success-text: "#256848"
  error-surface: "#ffedf0"
  error-text: "#a72e3a"
  paused-surface: "#fff0d9"
  paused-text: "#825108"
  role-surface: "#ffead1"
typography:
  display:
    fontFamily: '"Agora Display", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: "38px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.025em"
  headline:
    fontFamily: '"Agora Display", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: "30px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.025em"
  title:
    fontFamily: '"Agora Display", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: "19px"
    fontWeight: 600
    lineHeight: 1.4
  summary-title:
    fontFamily: '"Agora Display", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: "22px"
    fontWeight: 600
    lineHeight: 1.45
  body:
    fontFamily: '"Agora Text", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
  supporting:
    fontFamily: '"Agora Text", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.6
  rationale:
    fontFamily: '"Agora Text", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.8
  label:
    fontFamily: '"Agora Text", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: "14px"
    fontWeight: 500
    lineHeight: 1.5
  metadata:
    fontFamily: '"Agora Text", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  badge: "6px"
  status: "7px"
  compact-control: "9px"
  field: "10px"
  actor: "11px"
  inset: "12px"
  platform: "14px"
  surface: "16px"
  dialog: "20px"
  sidebar: "24px"
  mode-item: "26px"
  button: "28px"
  mode-container: "32px"
  circle: "50%"
spacing:
  "4": "4px"
  "6": "6px"
  "8": "8px"
  "10": "10px"
  "12": "12px"
  "14": "14px"
  "16": "16px"
  "18": "18px"
  "20": "20px"
  "22": "22px"
  "24": "24px"
  "26": "26px"
  "28": "28px"
  "30": "30px"
  "32": "32px"
  "36": "36px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    typography: "{typography.label}"
    rounded: "{rounded.button}"
    padding: "11px 19px"
  button-primary-hover:
    backgroundColor: "{colors.button-hover}"
  button-secondary:
    backgroundColor: "{colors.stone}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.button}"
    padding: "11px 19px"
  button-secondary-hover:
    backgroundColor: "{colors.secondary-hover}"
  button-text:
    backgroundColor: "transparent"
    textColor: "{colors.body}"
    padding: "4px 0"
  input:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.body}"
    rounded: "{rounded.field}"
    padding: "11px 13px"
    width: "100%"
  mode-navigation:
    backgroundColor: "{colors.stone}"
    rounded: "{rounded.mode-container}"
    padding: "4px"
  mode-navigation-active:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    typography: "{typography.label}"
    rounded: "{rounded.mode-item}"
    padding: "10px 19px"
  status:
    backgroundColor: "{colors.stone}"
    textColor: "{colors.body}"
    rounded: "{rounded.status}"
    padding: "5px 8px"
  status-success:
    backgroundColor: "{colors.success-surface}"
    textColor: "{colors.success-text}"
  status-error:
    backgroundColor: "{colors.error-surface}"
    textColor: "{colors.error-text}"
  status-paused:
    backgroundColor: "{colors.paused-surface}"
    textColor: "{colors.paused-text}"
  configuration-card:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
    padding: "28px"
  platform-card:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    rounded: "{rounded.platform}"
    padding: "18px 15px 14px"
  platform-card-selected:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
  actor-card:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.actor}"
    padding: "12px 8px"
    width: "100%"
  actor-card-selected:
    backgroundColor: "{colors.paper}"
  playback:
    backgroundColor: "{colors.stone}"
    rounded: "{rounded.platform}"
    padding: "12px 14px"
  model-dialog:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    rounded: "{rounded.dialog}"
    padding: "0"
    width: "calc(100% - 48px)"
---

# Design System: Agora Studio

## Overview

**Creative North Star: "The Warm Social Workbench"**

Agora Studio is a warm, clear workbench for configuring social simulations and observing an account's actions. The user's chosen [Refero Family reference](https://styles.refero.design/style/1bcae895-2245-4d33-aa43-1c1e80719554) informs its warm canvas, stone surfaces, rounded display lettering and confident black actions. Friendly details sit around precise controls; typography and tonal grouping keep configuration and replay easy to scan.

This system applies exclusively to the Developer and Viewer outer framework in `agora/web/studio.html`, `studio.css` and `studio.js`. Xiaohongshu, X/Twitter and Reddit iframe documents retain their own platform typography, color, layout and interaction. The platform identity marks within the studio are identifiers, not alternate studio themes. Keep the existing configuration, model connection, run history and account replay workflows intact when extending this framework.

**Key Characteristics:**

- Warm canvas and stone grouping surfaces, with white configuration and selected account surfaces.
- Rounded display lettering and clear bilingual controls with system Chinese fallbacks.
- Black capsule actions and mode selection; small bright cues communicate selection and status.
- Flat working surfaces, restrained borders and elevated transient overlays.
- A strict visual boundary around each native platform iframe.

Extraction sources are the built studio HTML, CSS and JavaScript; font provenance is recorded in `licenses/console-fonts.json` and the adjacent SIL OFL license files. Render evidence is in `.impeccable/review/developer/`, `viewer/` and `states/`. The token frontmatter is normative; sidecar tonal ramps are synthesized panel previews, not additional shipped color scales. `docs/design.md` remains the separate architecture document.

## Colors

The palette uses warm neutrals for most of the working area, with small functional color cues.

### Primary

- **Ink:** Titles, primary actions, active mode navigation, selected platform cards and the replay range use `ink`. The primary action hover uses `button-hover`.
- **Ember:** `accent` colors quiet link feedback and explanatory icons; `brand-orange` marks the logo dot and heading punctuation. Preserve these distinct implemented values.
- **Selection Yellow:** `selection-yellow` fills the selected platform check and browser text selection. It accompanies the selected card's dark surface.

### Neutral

- **Warm Canvas:** `canvas` is the document background, sticky masthead and form-control fill.
- **Stone:** `stone` groups summaries, Viewer filters, account and decision panels, and replay controls.
- **Paper:** `paper` carries configuration cards, selected account and timeline rows, and the platform viewport.
- **Body / Muted:** `body` carries supporting text and labels; `muted` carries secondary explanations and metadata.
- **Warm Line:** `line` separates structural areas. `card-line` provides the lighter configuration outline; `field-line` delineates controls; `field-focus` strengthens their focused edge.
- **Hover / Selected Neutrals:** `navigation-hover`, `navigation-selected` and `secondary-hover` preserve the small tonal differences in their source components. `selected-supporting` keeps secondary copy readable on selected platform cards.

### Functional color

- **Focus Blue:** `blue` is the keyboard focus outline and model connection test action.
- **Recorded Green:** `green` communicates connection, security and recorded outcomes. Successful run chips pair `success-surface` with `success-text`.
- **Error Rose:** `error-surface` and `error-text` communicate interrupted or failed runs; danger controls use the same error text.
- **Paused Amber:** `paused-surface` and `paused-text` communicate paused and pausing runs. `role-surface` distinguishes the main account role.

**The Native Boundary Rule.** Apply studio tokens to the outer framework only. Never inject its palette or typography into Xiaohongshu, X/Twitter or Reddit documents.

## Typography

**Display Font:** Bricolage Grotesque, served locally as **Agora Display**, with PingFang SC, Microsoft YaHei and sans-serif fallbacks.

**Body Font:** Inter, served locally as **Agora Text**, followed by the system stack recorded in the frontmatter. Chinese glyphs use the available system font.

**Character:** Rounded Latin display letters make the framework approachable. Body and controls remain direct and legible. Chinese headings retain a natural sans-serif voice through the fallback stack.

### Hierarchy

- **Display:** The `display` role is the Developer heading. It reduces to (32px) at widths up to (1280px), (30px) up to (760px), and (27px) up to (480px).
- **Headline:** The `headline` role is the Viewer run heading. It becomes (25px) up to (760px), then (20px) up to (480px) after the final source override. The narrow heading clamps to two lines; its subtitle truncates to one line. The full run name remains available in the heading's title attribute.
- **Title:** `title` describes configuration sections; the narrow size is (18px). `summary-title` describes the run summary. Empty state and dialog titles use (28px), with the dialog title reducing to (25px) on the narrow layout.
- **Body:** `body` supplies the page baseline; the Developer introduction is bounded to (62ch). Supporting descriptions use `supporting`; public rationale uses the more open `rationale` leading.
- **Label:** `label` describes primary and secondary actions, field labels and mode navigation. Text actions use (13px), weight (500).
- **Metadata:** `metadata` supplies (12px) supporting UI. Dense Viewer details also use (11px); numeric counters use tabular figures rather than a separate monospace brand font. Parameter JSON uses the browser's monospace `pre` presentation.

The observed scale is functional, not a geometric ratio. The logo is (34px), weight (700), reducing to (30px) and (28px) at the narrow breakpoints. The local display file declares weights (400–700); the body file declares (400–600). Both use `font-display: swap`; font synthesis is disabled.

**The Readable Control Rule.** Preserve the source's (16px) mobile field and select text at widths up to (480px), including the Viewer platform/run selectors and replay speed selector.

## Layout

The framework uses fluid columns with explicit minimum-width protection and scrollable dense lists. Its repeated spacing steps are recorded in the frontmatter; they represent observed values, not a requirement to force every distance onto an invented scale.

Developer has a centered maximum width of (1600px), a (194px) sidebar, and a flexible main area. The masthead is sticky, (84px) tall, with (36px) side padding. The main area uses (34px 36px 0) padding. Configuration uses a flexible form plus a (288px) sticky summary and a (24px) gap. Configuration cards have (28px) padding and (20px) separation; field grids use two or three columns with an (18px) gap. Platform options stay a three-column choice group.

Viewer has a centered maximum width of (1720px), (30px 32px) page padding, and a workspace grid of (186px / flexible / 280px) with (20px) gaps. The flexible platform stage owns the largest area. Account and timeline lists scroll within their panels. The platform iframe is (690px) tall at the default desktop size and (760px) from (1600px) upward; window chrome is (34px) tall.

Responsive behavior comes from these actual media queries:

- **Up to (1280px):** Developer sidebar becomes (176px), summary (264px), configuration gap (18px), and card padding (22px). Viewer side columns become (164px / 260px), with (16px) gaps and (24px) page side padding.
- **Up to (1100px):** Developer sidebar disappears and the main area centers within (1040px). Viewer retains (170px) account plus flexible stage columns, moving the decision panel underneath with two internal columns for detail and timeline.
- **Up to (760px):** Header becomes (72px). Developer form and summary stack; the summary becomes static. Viewer stacks account selection, stage and decision panel in that order. Account choices become a horizontal scroll strip with (156px) cards; the iframe is (660px) tall. Recent runs collapse into compact rows.
- **Up to (480px):** Header becomes (68px). Developer side padding is (16px); ordinary fields stack, while its short three-number budget grid remains three columns. The model dialog's budget fields stack. Viewer side padding is (12px), workspace gap (14px), iframe height (620px). The compact filter grid uses (104px / flexible) columns; extra toolbar status and creation links disappear. Replay controls wrap, with (28px) step circles and a (32px) play circle after the final override.

On the narrow Developer screen, model connection and launch actions remain in a fixed bottom bar with safe-area padding; the page reserves bottom space. The single existing launch button is positioned into this bar. On Viewer, expanded stage mode hides outer account and decision panels and gives the same iframe a full-width column. Expanded iframe height is (760px) on desktop, (660px) up to (760px), and (700px) up to (480px), following the cascade. Expanding does not recreate the iframe or reset the historical step.

## Elevation & Depth

Working surfaces are flat at rest. Warm tonal layering distinguishes canvas, grouped panels and selected rows; thin borders define controls and the native viewport. Shadows are reserved for the model dialog and toast. The sticky header and fixed launch bar use borders and stacking, without ambient card shadows.

### Shadow Vocabulary

- **Dialog:** `0 16px 56px #12121230` lifts the modal configuration surface. Its backdrop is `#24201966`.
- **Toast:** `0 6px 24px #12121220` lifts transient feedback above the working surface.

Buttons, links and platform cards transition background, text and border color over (160ms ease-out). Toast opacity and vertical position use the same timing. The implementation has no page entrance choreography. Reduced-motion preference disables transitions and animation and restores automatic scroll behavior.

**The Flat Workbench Rule.** Keep persistent configuration and observation surfaces flat; use elevation for transient overlays.

## Shapes

The source's shared surface radius is (16px). Configuration, summary, account/decision containers, recent runs and platform windows use that recurring shape. Inset content uses (10–14px) corners; the model dialog opens to (20px). Badges use (6–7px), while navigation and actions use longer (24–32px) capsule contours. Circular avatars, selection checks and replay controls remain circles.

The shape vocabulary reflects component role: rounded containers group information, capsules identify actions, compact rectangles identify status. The native window clips its contents at the frame boundary; only the outer wrapper receives studio corners. Default line weight is (1px). Icons are stroked SVGs, usually (20px), with stroke width (1.7), round caps and round joins; compact controls reduce icon size to (14–18px).

## Components

### Buttons

Confident capsules with concise sentence-case labels. Primary and secondary variants use (44px) minimum height, (11px 19px) padding, a (9px) icon gap and the frontmatter's button radius. Primary uses ink and paper; secondary uses stone, ink and a warm line. Their source hover variants are separately tokenized. Text actions are transparent, padded (4px 0), and shift to accent on hover. Disabled buttons use opacity (0.45) and a default cursor. Focus-visible uses a (2px) blue outline offset (4px). The source does not add a separate pressed-state transform.

### Chips and status

Small rectangular status markers combine text with a current-color dot. Base status uses (5px 8px) padding and (12px) type. Running and completed share success treatment; failed and interrupted share error; paused and pausing share amber. Other states keep the neutral base. Count and role markers are smaller rectangles. Status stays textual so its meaning is not dependent on color alone.

### Cards and containers

Configuration cards use paper, a light warm outline and the shared surface radius. Summary and Viewer context panels use stone. Selected account and timeline rows use paper against their stone parent. Configuration card padding reduces with the breakpoints recorded in Layout; no hover lift or shadow is applied to persistent containers.

### Inputs and fields

Warm canvas fields use the field radius, warm control line, (44px) minimum height, (11px 13px) padding and (14px) body text. Labels use weight (500), with a (9px) label/control gap. Focus strengthens the border and uses the global blue outline with a closer (2px) offset. Placeholders use muted text at full opacity. Textareas resize vertically and use (1.7) leading. The count stepper keeps (44px) decrement/increment segments around a centered input and applies stone hover feedback. Its input has an explicit label and an `aria-describedby` connection to the inclusion hint; stepper buttons have action labels. HTML validation and status feedback remain the existing error mechanisms; no additional field-error skin is established.

### Navigation

Mode navigation is a stone capsule with (4px) inner padding; active mode becomes an ink capsule with paper text. Inactive mode text is muted and receives the navigation hover fill. Sidebar navigation is a quieter capsule with body text, an (18px) icon, and a warm selected background. It disappears at the established tablet breakpoint, while the top mode switch remains. On the narrow layout, mode icons disappear and textual mode labels stay visible.

### Platform choice

Three compact platform cards retain their native identity marks. A selected option switches the whole card to ink, supporting copy to the selected-supporting neutral, and its circular check to selection yellow. Unselected cards use warm canvas and a thin warm border; hover strengthens that border. The control is a semantic button with `aria-pressed`. On the narrow layout, descriptions and secondary platform captions disappear while marks, names and selection checks stay visible.

### Account selection and timeline

Account rows combine a circular initial avatar, name and compact role/action metadata. Selection uses paper; hover uses a warmer neutral. Account choice buttons expose selection through `aria-pressed`. Names truncate within the available space. On mobile the same choices become horizontally scrollable cards. Timeline rows use the same tonal selection language; the selected step number uses accent and the selected row has `aria-current="step"`. Public rationale sits in a warm canvas inset with (16px) padding and open leading; overlong text and parameter JSON wrap.

### Playback and native platform window

Playback lives in a stone rounded strip above the native viewport. Previous/next actions are light circles; play is the dark focal circle. The slider uses ink, the step count uses tabular figures, and speed/latest remain compact labeled controls. Buttons disable at trajectory boundaries. Latest has a green selected state; historical selection changes the observation associated with the same account window. The frame's read-only label describes actual behavior and stays in the outer chrome.

### Model dialog and feedback

The native HTML dialog is named by its visible heading through `aria-labelledby`. It has a maximum width of (800px), viewport-bounded height, the frontmatter's dialog radius, a shadow and darkened backdrop. It uses the same field and button vocabulary as the page. Its desktop header padding is (30px 32px 22px); body padding is (0 32px 30px), reducing at narrow breakpoints. Saved model choices wrap; long labels wrap within them. The narrow footer wraps and gives the save action full width. The toast is an ink rounded rectangle with paper text and polite live status; mobile placement clears the launch bar.

## Do's and Don'ts

### Do:

- **Do** apply these tokens only to the Developer and Viewer outer framework.
- **Do** use warm canvas for the workbench, stone for grouped controls and paper for configuration or selected rows.
- **Do** keep primary actions and active mode selection in ink capsules with paper text.
- **Do** preserve visible keyboard focus, textual status labels and the source's readable mobile form text.
- **Do** preserve account, step and iframe identity when changing the outer Viewer layout.
- **Do** retain the local font files, provenance manifest and SIL OFL notices when shipping the typography.

### Don't:

- **Don't** restyle Xiaohongshu, X/Twitter or Reddit iframe documents with the studio system.
- **Don't** add shadows to persistent configuration or observation cards.
- **Don't** replace configuration or replay actions with decorative surfaces or motion.
- **Don't** treat synthetic demonstration data as evidence of actual user behavior or model capability.
- **Don't** interpret the sidecar's synthesized tonal ramps as new production color tokens.
