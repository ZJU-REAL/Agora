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
  mode-surface: "#f0f2fc"
  mode-selected: "#3d486f"
  sidebar-selected: "#e9efff"
  sidebar-selected-ink: "#4059a4"
  card-line: "#e4e9f4"
  field-line: "#dce2ef"
  field-focus: "#8c9dc8"
  heading-surface: "#eff2ff"
  heading-accent: "#5365ad"
  heading-copy: "#586489"
  summary-surface: "#f1f0fc"
  summary-divider: "#dbe2f1"
  summary-ready: "#e6e9fa"
  actor-surface: "#f0f3fd"
  decision-surface: "#f5f6ff"
  row-selected: "#e5ecff"
  viewer-heading-surface: "#f0f3ff"
  toolbar-surface: "#f2f4fc"
  playback-surface: "#eef2ff"
  playback-action: "#42507d"
  dialog-surface: "#fcfdff"
  platform-pink: "#fff4f8"
  platform-pink-selected: "#ffe8f1"
  platform-pink-line: "#f1dce6"
  platform-pink-selected-line: "#c9658b"
  platform-blue: "#f0f5ff"
  platform-blue-selected: "#e3edff"
  platform-blue-line: "#dee7f8"
  platform-blue-selected-line: "#6f8dc6"
  platform-peach: "#fff5ec"
  platform-peach-selected: "#ffecd9"
  platform-peach-line: "#f0e3d7"
  platform-peach-selected-line: "#c48652"
  platform-selected-ink: "#26304b"
  platform-selected-copy: "#5d627c"
  selected-check: "#5262a0"
  success-surface: "#e6f2e9"
  success-text: "#256848"
  error-surface: "#ffedf0"
  error-text: "#a72e3a"
  paused-surface: "#fff0d9"
  paused-text: "#825108"
  role-surface: "#ffead1"
  selection-yellow: "#ffcd6c"
typography:
  display:
    fontFamily: '"Agora Display", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 36px
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: -0.025em
  headline:
    fontFamily: '"Agora Display", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 30px
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: -0.025em
  title:
    fontFamily: '"Agora Display", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 19px
    fontWeight: 600
    lineHeight: 1.4
  summary-title:
    fontFamily: '"Agora Display", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 22px
    fontWeight: 600
    lineHeight: 1.45
  body:
    fontFamily: '"Agora Text", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.5
  supporting:
    fontFamily: '"Agora Text", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.6
  rationale:
    fontFamily: '"Agora Text", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.8
  label:
    fontFamily: '"Agora Text", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.5
  metadata:
    fontFamily: '"Agora Text", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.5
rounded:
  badge: 6px
  status: 7px
  compact-control: 9px
  field: 10px
  actor: 11px
  inset: 12px
  platform: 14px
  surface: 16px
  viewer-heading: 18px
  hero-dialog: 20px
  sidebar: 24px
  mode-item: 26px
  button: 28px
  mode-container: 32px
  circle: 50%
spacing:
  "4": 4px
  "6": 6px
  "8": 8px
  "10": 10px
  "12": 12px
  "14": 14px
  "16": 16px
  "18": 18px
  "20": 20px
  "22": 22px
  "24": 24px
  "26": 26px
  "28": 28px
  "30": 30px
  "32": 32px
  "36": 36px
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    typography: "{typography.label}"
    rounded: "{rounded.button}"
    padding: 11px 19px
  button-primary-hover:
    backgroundColor: "{colors.button-hover}"
  button-secondary:
    backgroundColor: "{colors.stone}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.button}"
    padding: 11px 19px
  button-secondary-hover:
    backgroundColor: "{colors.secondary-hover}"
  button-text:
    backgroundColor: transparent
    textColor: "{colors.body}"
    padding: 4px 0
  button-text-hover:
    textColor: "{colors.accent}"
  input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.body}"
    rounded: "{rounded.field}"
    padding: 11px 13px
    width: 100%
  mode-navigation:
    backgroundColor: "{colors.mode-surface}"
    rounded: "{rounded.mode-container}"
    padding: 4px
  mode-navigation-active:
    backgroundColor: "{colors.mode-selected}"
    textColor: "{colors.paper}"
    typography: "{typography.label}"
    rounded: "{rounded.mode-item}"
    padding: 10px 19px
  status:
    backgroundColor: "{colors.stone}"
    textColor: "{colors.body}"
    rounded: "{rounded.status}"
    padding: 5px 8px
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
    padding: 28px
  platform-pink:
    backgroundColor: "{colors.platform-pink}"
    textColor: "{colors.ink}"
    rounded: "{rounded.platform}"
    padding: 18px 15px 14px
  platform-pink-selected:
    backgroundColor: "{colors.platform-pink-selected}"
    textColor: "{colors.platform-selected-ink}"
    rounded: "{rounded.platform}"
    padding: 17px 14px 13px
  platform-blue:
    backgroundColor: "{colors.platform-blue}"
    textColor: "{colors.ink}"
    rounded: "{rounded.platform}"
    padding: 18px 15px 14px
  platform-blue-selected:
    backgroundColor: "{colors.platform-blue-selected}"
    textColor: "{colors.platform-selected-ink}"
    rounded: "{rounded.platform}"
    padding: 17px 14px 13px
  platform-peach:
    backgroundColor: "{colors.platform-peach}"
    textColor: "{colors.ink}"
    rounded: "{rounded.platform}"
    padding: 18px 15px 14px
  platform-peach-selected:
    backgroundColor: "{colors.platform-peach-selected}"
    textColor: "{colors.platform-selected-ink}"
    rounded: "{rounded.platform}"
    padding: 17px 14px 13px
  actor-card:
    backgroundColor: transparent
    textColor: "{colors.ink}"
    rounded: "{rounded.actor}"
    padding: 12px 8px
    width: 100%
  actor-card-selected:
    backgroundColor: "{colors.row-selected}"
  playback:
    backgroundColor: "{colors.playback-surface}"
    rounded: "{rounded.platform}"
    padding: 12px 14px
  run-summary:
    backgroundColor: "{colors.summary-surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
    padding: 26px
  illustrated-heading:
    backgroundColor: "{colors.heading-surface}"
    textColor: "{colors.ink}"
    typography: "{typography.display}"
    rounded: "{rounded.hero-dialog}"
    padding: 20px 26px
  viewer-heading:
    backgroundColor: "{colors.viewer-heading-surface}"
    textColor: "{colors.ink}"
    typography: "{typography.headline}"
    rounded: "{rounded.viewer-heading}"
    padding: 18px 20px
  brand-wordmark:
    width: 184px
    height: 72px
  model-dialog:
    backgroundColor: "{colors.dialog-surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.hero-dialog}"
    padding: "0"
    width: calc(100% - 48px)
---

# Design System: Agora Studio

## Overview

**Creative North Star: "The Illustrated Social Workbench"**

Agora Studio is a clear social-world workbench with an illustrated, anime-influenced identity. The user-supplied Agora wordmark and world illustration establish the personality: cool indigo drawing, blue and lavender planes, and small pink, peach and golden details. A near-white working canvas and readable controls give the artwork room without making configuration or replay visually busy.

This design system applies exclusively to the Developer and Viewer outer framework in `agora/web/studio.html`, `studio.css` and `studio.js`. Xiaohongshu, X/Twitter and Reddit iframe documents retain their native typography, color, layout and interaction. The illustrated identity belongs to branding and orientation; account actions, observations, counts and public rationales remain actual interface content.

**Key Characteristics:**

- Official illustrated image branding, reused at appropriate sizes rather than redrawn as a CSS logo.
- Near-white canvas, indigo ink, blue and lavender grouping surfaces, and restrained pastel platform choices.
- Rounded Latin headings and legible bilingual controls with self-hosted fonts and system Chinese fallbacks.
- Flat working surfaces, fine outlines, capsule actions and brief state transitions.
- A strict visual boundary around each native social-platform iframe.

The token frontmatter is normative and records values actually used by the final source cascade. Extraction sources are the studio HTML, CSS and JavaScript, checked against desktop, mobile, (1024px) Developer and (800px) Developer/Viewer captures in `.impeccable/review/playful-developer/` and `playful-viewer/`. `.impeccable/design.json` extends this document with shadows, motion, breakpoints and source-derived component previews; its synthesized tonal ramps are panel aids, not a shipped color scale. `docs/design.md` remains the separate architecture document. This refresh captures the user's expressly requested replacement of the earlier plain warm treatment.

## Colors

The palette follows the approved illustrated branding: indigo drawing and cool working planes, with limited pink and peach for choice and small warm functional cues. Keep the source token names, including `stone`, even though the current grouping surface is cool.

### Primary

- **Indigo Ink:** `ink` carries headings, primary actions and the replay range. `button-hover` supplies its brighter hover state. `mode-selected` is the distinct active navigation fill, and `playback-action` fills the replay play control.
- **Periwinkle Accent:** `accent` supplies text-action feedback and explanatory icons. `heading-accent` highlights the Developer title. `blue` supplies the keyboard focus outline and model connection test action.
- **Selection Indigo:** `selected-check` fills the checked platform indicator with a white tick. This accompanies the selected platform's stronger border, pastel fill and pressed state.

### Secondary

- **Blue and Lavender Planes:** `heading-surface` introduces the illustrated Developer title; `viewer-heading-surface` frames the Viewer title; `summary-surface` groups the launch summary. `actor-surface`, `decision-surface`, `toolbar-surface` and `playback-surface` distinguish their working regions without shadows.
- **Selected Row Blue:** `row-selected` highlights the selected account and historical timeline action. Selected rows remain legible within their own cool panel surfaces.

### Tertiary

- **Platform Rose:** `platform-pink` and `platform-pink-selected` identify the Xiaohongshu choice; its line tokens distinguish resting and selected edges.
- **Platform Sky:** `platform-blue` and `platform-blue-selected` identify X/Twitter, with the matching line tokens.
- **Platform Peach:** `platform-peach` and `platform-peach-selected` identify Reddit, with the matching line tokens.
- **Selected Platform Copy:** `platform-selected-ink` and `platform-selected-copy` retain dark text on the selected pastel choice. Native red, black and orange platform marks remain identifiers; they are not alternate studio action colors.
- **Functional Status:** success, error and paused token pairs communicate real run state. `green` marks connection and recorded outcomes. `role-surface` supports the small main-account role marker. `selection-yellow` remains browser text selection, not the platform check fill.

### Neutral

- **Cloud Canvas:** `canvas` is the document background and several small Viewer controls. The masthead, configuration cards, ordinary form fields, summary inset and native viewport use `paper`.
- **Cool Grouping Surface:** `stone` supports secondary actions, navigation hover, small control surfaces and window chrome where the component has no more specific plane.
- **Indigo Gray Copy:** `body` carries body text and labels; `muted` carries secondary explanations, account/timeline metadata and the window address; these roles share the final accessible source color. `heading-copy` is the distinct Developer introduction color.
- **Fine Cool Lines:** `line` separates structural regions. `card-line` outlines configuration cards, `field-line` defines controls, and `field-focus` strengthens the focused field border. `summary-divider` divides the launch summary.
- **Transient Surfaces:** `dialog-surface` is the model dialog and mobile launch-bar fill. Hover and navigation tokens preserve source state differences; do not flatten them into one guessed neutral.

**The Native Boundary Rule.** Apply these tokens to the outer framework only. Preserve the independent visual system inside each platform iframe.

## Typography

**Display Font:** Bricolage Grotesque, served locally as **Agora Display**, with PingFang SC, Microsoft YaHei and sans-serif fallbacks.

**Body Font:** Inter, served locally as **Agora Text**, followed by the system stack in the frontmatter. Chinese glyphs use the available system font.

**Character:** Rounded Latin headings sit naturally alongside the illustrated identity; body text and controls stay direct and readable. The brand itself is an image wordmark, so its lettering does not become a reusable CSS text role.

### Hierarchy

- **Display:** `display` records the final Developer heading (36px, weight 600, leading 1.45). Its final responsive sizes are (30px) up to (1280px), (28px) up to (800px), and (25px, leading 1.5) up to (480px). Earlier generic heading sizes are overridden by these illustrated-heading rules.
- **Headline:** `headline` records the Viewer run heading. It becomes (25px) up to (760px) and (19px) up to (480px), after the illustrated-heading override. The narrow title clamps to two lines and the subtitle truncates to one; the full run name remains in the heading's title attribute.
- **Title:** `title` describes configuration sections and becomes (18px) up to (480px). `summary-title` describes the launch summary; it becomes (20px) from (761px) to (1280px) and remains (22px) below that range. Viewer empty-state and dialog titles use (28px); the dialog title becomes (25px) on the narrow layout.
- **Body:** `body` supplies the page baseline. The Developer introduction is bounded to (48ch), becomes (14px) up to (800px), and ends at (14px, leading 1.65) up to (480px). Supporting descriptions use `supporting`; public rationale uses the more open `rationale` leading.
- **Label:** `label` describes primary and secondary actions, field labels and mode navigation. Text actions use (13px, weight 500); compact mode items use (12px) on the narrow layout.
- **Metadata:** `metadata` supplies secondary UI. Dense Viewer details also use (11px); numeric counters use tabular figures. Parameter JSON uses a browser monospace presentation rather than a separate branded font.

The scale is functional rather than geometric. The display font declares weights (400–700), the body font (400–600); both use `font-display: swap` and font synthesis is disabled. Preserve the existing self-hosted files and licenses in `licenses/console-fonts.json` and the adjacent SIL OFL files.

**The Readable Control Rule.** Preserve the implemented mobile field and select text size (16px), including platform, experiment and replay-speed selectors.

## Layout

The framework uses fluid columns with explicit minimum-width protection and bounded scrolling for dense lists. The spacing steps in the frontmatter are observed recurring values, not an invented uniform grid. Illustrated identity planes introduce the page; form and replay areas then carry the working density.

Developer centers within (1600px) with a (194px) sidebar and flexible main area. Its sticky masthead is (84px) tall with (36px) side padding; the main area uses (34px 36px 0) padding. The illustrated heading has a (170px) minimum height, (20px 26px) padding and a (24px) bottom gap. Its copy is flexible, bounded to (690px), beside a (220px by 144px) illustration region. The image preserves its aspect ratio within that region. Configuration pairs the flexible form with a (288px) sticky summary and a (24px) gap. White cards use (28px) padding and (20px) separation. Field grids use two or three columns with an (18px) gap; the platform choice group remains three columns.

Viewer centers within (1720px) with (30px 32px) page padding. Its title plane uses (18px 20px) padding. The working grid is (186px / flexible / 280px) with (20px) gaps; the platform stage owns the largest area. Account and timeline lists scroll within their panels. The native iframe is (690px) tall by default and (760px) from (1600px) upward; window chrome is (34px) tall.

Responsive behavior follows the final cascade:

- **Up to (1280px):** Developer sidebar becomes (176px), summary (264px), grid gap (18px) and card padding (22px). Its hero becomes at least (152px) tall with (18px 22px) padding; illustration region becomes (170px by 128px), with a (164px by 148px) contained image. Viewer side columns become (164px / 260px) with (16px) gaps and (24px) page side padding. Between (761px) and (1280px), summary spacing tightens along with its title.
- **Up to (1100px):** Developer sidebar disappears and its main area centers within (1040px). Viewer retains a (170px) account column and flexible stage, moving the decision panel underneath with two internal columns for detail and timeline.
- **Up to (800px):** Wordmark display becomes (170px by 66px). Developer illustration region narrows to (150px) and the image to (148px by 134px). These identity changes precede the working-layout stack breakpoint.
- **Up to (760px):** Header becomes (72px). Developer form and summary stack and the summary becomes static. Viewer stacks account selection, stage and decision panel in that order; account choices form a horizontal strip of (156px) cards. The iframe becomes (660px) tall. Recent runs use compact rows.
- **Up to (480px):** Header becomes (68px), wordmark (158px by 62px), Developer side padding (16px) and Viewer side padding (12px). Hero copy is bounded to (70%) beside a small absolutely placed image region, finally (102px) wide at right (3px); the image ends at (104px by 100px). The hero has (20px 16px) padding and a (170px) minimum height. Platform descriptions hide but all three choices remain visible. Ordinary fields stack; the short three-number budget grid stays three columns, while the model dialog's budget fields stack. Viewer filters use (104px / flexible) columns; extra toolbar status and creation links hide. Workspace gap becomes (14px) and iframe height (620px). Replay wraps with final (28px) step circles and a (32px) play circle.

On narrow Developer screens, model connection and launch remain in the fixed bottom bar with safe-area padding; the document reserves bottom space. The same existing launch button is positioned there. The launch summary title remains visible after the final override.

Expanded Viewer mode hides outer account and decision panels and gives the same iframe a full-width column. Expanded height is (760px) on desktop, (660px) up to (760px), and (700px) up to (480px), following the cascade. Expansion preserves the selected account, historical step and iframe identity.

## Elevation & Depth

Working surfaces are flat at rest. Blue and lavender tonal planes distinguish groups; fine borders define fields, configuration cards and the native viewport. Shadows are reserved for transient overlays. The sticky masthead and mobile launch bar use borders and stacking rather than ambient shadow.

### Shadow Vocabulary

- **Dialog:** `0 16px 56px #12121230` lifts the model configuration dialog; its backdrop uses `#24201966`.
- **Toast:** `0 6px 24px #12121220` supports temporary feedback. The toast moves (10px) and fades over (160ms ease-out).

Buttons, links and platform choices transition background, color and border color over (160ms ease-out). There is no continuous decorative motion. The reduced-motion media query disables transitions and animation and restores automatic scrolling.

## Shapes

The form language combines rounded rectangular planes, capsule actions and circular small controls. Configuration and viewport surfaces use `surface`; the Developer illustrated plane and model dialog use `hero-dialog`; Viewer title planes use `viewer-heading`. Form fields use `field`, platform choices `platform`, account rows `actor`, and inset rationale/summary regions `inset`. Navigation and buttons use the capsule radii recorded in the frontmatter. Selected platform choices strengthen their edge to (2px) and reduce padding by (1px) to preserve geometry.

The official branding is raster artwork with transparent edges and `object-fit: contain`. Preserve its proportions and detail; do not recreate its silhouette with CSS geometry. Two small outlined stars and a dot accompany the Developer illustration. These are static accents, not another mascot system; the smaller star hides on mobile.

## Components

### Branding and illustrated headings

The official wordmark is the header link, with an accessible Agora home label and image alternative text. It uses `agora/web/agora-wordmark.webp`; the compact sidebar icon uses `agora/web/agora-mark.png`; Developer heading and Viewer empty state use `agora/web/agora-world.webp`. The favicon uses `agora/web/agora-favicon.png`. Application markup resolves these through `/static/` and its existing deployment routing.

The user supplied `agora_icon.png` and `agora_text.png` as the official identity. Their derivatives crop transparent padding and resize proportionally; they do not repaint the artwork. Original supplied PNGs remain unchanged. Source and transformation hashes are recorded in `licenses/agora-artwork.json`. Keep this provenance when making further derivatives. Decorative hero and empty-state images remain hidden from assistive technology; the working title and action carry the meaning.

**The Honest Illustration Rule.** Use the approved Agora artwork for branding and orientation. Never present illustration as account data, a simulation outcome or evidence of model capability.

### Buttons

Capsule actions are calm and definite. Primary actions pair `ink` and `paper`; secondary actions pair `stone` and `ink` with a fine outline. Both use `label`, `button` radius, (11px 19px) padding and a (44px) minimum height. Their hover fills are the dedicated frontmatter variants. Text actions are transparent with body-colored text and periwinkle hover. Keyboard focus uses a (2px) blue outline with (4px) offset. Disabled buttons reduce opacity to (0.45) and use the default cursor.

### Inputs / Fields

White, gently curved fields use `field-line`, `field` radius, (11px 13px) padding and a (44px) minimum height. Focus changes the edge to `field-focus` and offsets the same blue outline by (2px). Placeholder and helper copy use `muted`. Textareas resize vertically with open leading. The number control is one bordered container with (44px) decrement/increment buttons around a centered input. Preserve the explicit total-agent label and associated hint; do not rely on decorative text for an input name.

### Navigation

The mode switch is a cool capsule containing two rounded links. Active mode uses `mode-selected` with white text; inactive mode uses muted copy and `navigation-hover` on hover. Sidebar selection uses `sidebar-selected` with `sidebar-selected-ink`; sidebar hover uses `stone`. The sidebar hides at the working-layout breakpoint while the mode switch remains. On the narrow layout, mode icons hide and text labels stay visible.

### Chips

Small badges use compact radii and cool fills. Run-status chips use `status`, a small current-color dot and explicit text; success, error and paused variants use their paired tokens. Color never replaces the written status. Main-account role badges use the small warm role surface. Selected platform indicators use an indigo circle with a white check, and their buttons carry `aria-pressed`.

### Cards / Containers

Configuration cards are white, finely outlined, flat surfaces. The launch summary uses its lavender plane with a white selected-platform inset and experiment-name field; its heading shares a row with a small circular play motif. Account and decision panels use separate cool fills. Public rationale remains a white inset, while dense parameters use a bounded, scrollable monospace block.

Platform choices retain their native identity marks within the studio's pink, blue and peach choice surfaces. A selected choice keeps dark title and description copy, uses the matching stronger border, and shows the indigo check. Platform caption text wraps at intermediate widths; mobile hides descriptions and captions while preserving names, marks and selection.

### Account selection and exact replay

Account choices combine a small circular avatar, one-line name, role and action count. Their selected fill is `row-selected`; unselected hover uses `navigation-hover`, while the selected fill remains. Pressed state tracks the selected account. The narrow account list scrolls horizontally rather than compressing names and controls.

Replay places circular previous/play/next controls beside the native range, step count, speed and latest-state action. Its cool plane and indigo play button keep the control bar visible above the platform viewport. Expansion is a pressed-state action with an accessible label for both expanded and restored states. It changes the outer grid only: keep the same iframe and precise historical step. Native platform content remains independent of this component system.

### Model dialog and feedback

The dialog uses `dialog-surface`, the generous rounded shape and the transient shadow above. Its title is explicitly associated through `aria-labelledby`; maintain that relationship. The dialog width starts at `calc(100% - 48px)` with an (800px) maximum and narrows its outer margins at mobile breakpoints. Its scroll height is bounded by the viewport. Model security feedback uses a green-tinted inset, saved model choices wrap, and feedback/toast regions retain status semantics. The toast uses indigo with white copy and respects the mobile launch bar's occupied space.

## Do's and Don'ts

### Do:

- **Do** reuse the supplied Agora wordmark and icon/world derivatives, preserving proportions, illustration detail and transparent edges.
- **Do** keep the near-white canvas and indigo text as the framework baseline; use blue and lavender planes to group work.
- **Do** keep the three platform choices distinct with their implemented pink, blue and peach surfaces, borders and pressed states.
- **Do** retain keyboard focus outlines, associated field labels, the dialog title, actor pressed states and readable mobile controls.
- **Do** preserve the selected historical step and the same iframe when expanding or restoring the platform stage.
- **Do** use short state transitions and respect reduced-motion preferences.

### Don't:

- **Don't** return to the rejected single warm-yellow form treatment or the earlier terracotta-and-stone framework palette.
- **Don't** replace the illustrated wordmark with the obsolete CSS brand-mark or a text-only approximation.
- **Don't** generate replacement mascot art or copy third-party cartoon characters; extend the approved artwork vocabulary with restrained color and simple accents.
- **Don't** apply studio typography, palette or decorative artwork to the native social-platform documents.
- **Don't** add ambient shadows to every working card or continuous floating, particle or looping animation.
- **Don't** let artwork overlap labels, choices, launch actions or replay controls at narrow widths.
