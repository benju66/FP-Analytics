# FP MCP and MCP Apps in Claude: investigation notes

Session date: 2026-11-12. These notes capture a research session so the work can be continued locally.
Open `mockups.html` in this folder in a browser to see the wireframes.

## Start here (for whoever continues this)

- **Nothing has been built.** This session produced research, a list of possibilities and wireframes only.
- **The FP MCP server's source was not available.** It is not in this repository, and a code search of the
  owner's GitHub repositories found nothing. Everything said about the server comes from its tool
  descriptions as seen through the connector. Verify against the real code first.
- **Unverified items** are listed at the end. The most important one is whether the organization has access
  to the gated preview features.
- **Suggested first task:** port the staffing dashboard to an MCP App view (see "Suggested order").

## What was announced (2026-11-10)

Anthropic announced "interactive connectors": a supported tool can open beside the conversation or full
screen, and Claude can make changes in it. For developers, Claude now supports more of the MCP Apps
extension, including app tools and embedded sites. The capabilities are in public preview and
implementation details may change. Rollout is on web and desktop, on all plans, as accounts are updated.

## Where FP MCP stands today

- **No MCP App.** As far as the tool descriptions show, FP MCP has no `ui://` resources. Its dashboard tools
  return links to separate pages:
  - `open_bid_dashboard` returns a link to a shared claude.ai page that reads BuildingConnected live.
  - `open_staffing_dashboard`, `open_bid_dashboard_with_results` and `open_bid_dashboard_legacy` return
    links to server-built snapshot pages that work for about a day.
  - The project dashboard is a live dashboard link fed by `get_project_dashboard_data`.
- **Custom connector.** It was assumed that FP MCP is added by URL and has no directory listing. If it has a
  Community listing, entry points and embedded sites are blocked.
- **Server language.** The tool schemas look like a Python server. The MCP Apps SDK for the view is
  JavaScript. Helper support on a Python server was not checked.

## Capabilities and access for a custom connector

| Capability | What it does | Access |
| --- | --- | --- |
| Inline view | UI rendered in the conversation | No organization gate stated |
| Side panel / full screen | View stays open beside the chat | Limited set of organizations; falls back to full screen |
| Entry points | Open from the Artifacts page, pin to sidebar | Limited set of organizations; Verified or custom connectors only |
| App tools | Claude changes what the open view shows | Limited set of organizations |
| Messages (`app.sendMessage`) | A button in the view sends Claude a request | No gate stated; the user must agree to each message |
| Downloads (`app.downloadFile`) | View saves a file to the device | Varies by where the view appears; the user confirms |
| Embedded sites | Your own site in an iframe | Limited set of organizations; the user allows each origin |

Conditions that apply to the gated features:

- The account needs the unified Claude experience (chat and Cowork combined). On Team and Enterprise an
  Owner controls this under Organization settings > Capabilities.
- The connector must be remote. Local servers get none of this.
- When access is missing there is no error. The feature just does not appear, so keep a fallback.
- The only way to learn whether an organization has access is to test.

Directory connectors, for comparison: a Verified listing gets entry points and embedded sites (only for
origins the listing allows). A Community listing gets neither.

## Possibilities for FP MCP

### Dashboards that live in Claude
- Bid, staffing and project dashboards as views in the side panel, with live data in place of a link that
  expires.
- Claude drives the open page: "show coverage for E26-292" switches the tab and estimate.
  `open_bid_dashboard` already takes `view` and `estimate`, which map directly to app tools.
- Pinned apps: "Bid dashboard" and "Staffing board" in the sidebar, opened without a prompt.

### Draft-and-confirm editors
- RFIs, submittals, change events, meetings: the draft appears as a form. Claude fills fields, the person
  edits, and a Save button commits.
- Commitments, change orders, subcontractor invoices, budget forecasts and transfers: the same pattern with
  line items in an editable grid.
- BuildingConnected estimate setup as a three-step wizard (project, bid packages, publish package).
- Add project contacts as a picker over the company Directory.

### Viewers
- Drawing sheets with pan and zoom; Claude can jump to a sheet or region. See "Drawing viewer" below.
- Documents, specs and the prime contract in a page reader, with the schedule of values as a table.
- Starred photos as an inline carousel, which also works on mobile.

### Decision tools
- Superintendent what-if: click a candidate to see the weeks it pushes them over.
- Budget snapshot comparison, project schedule lookahead, RFI and submittal performance as interactive
  charts.

### Document builders
- Owner weekly update: live letter preview, photo picker, warnings fixed in place, then download the Word
  file.
- Weekly schedule and forecast workbook: progress through the steps, then download.

### View-to-Claude buttons
- "Draft an RFI about this detail" on a drawing, or "explain this variance" on a budget line. The text
  lands in the person's message box for them to send.

### Other
- Admin usage dashboard from `get_connector_usage`.
- The same app runs in any AI application that supports MCP Apps.

## Drawing viewer: real sheets or not

The wireframe's floor plan is a placeholder. A real viewer has two sources:

- **Sheet pictures.** `get_drawing_sheet` returns an image of the real Procore sheet (whole or one quarter)
  plus the text Procore read off it. True sheet, fixed zoom levels.
- **Sheet PDFs.** `get_design_files` hands out private download links to the per-sheet PDFs, currently only
  for the save-to-folder script. Rendering those gives sharp pan and zoom. It needs server work: the view
  runs in a sandbox, so the server must pass the PDF through its own tool or an allowed origin, and large
  sheets may need tiling.

Limits either way: current revision by default, Procore markups are not readable, and it is not to scale.

## Constraints that shape the design

- **Save buttons bypass Claude's approval prompt.** When a view calls the server's own tools with
  `app.callServerTool`, the user sees no prompt. The button must be the confirmation.
- **Embedded sites are a poor fit.** Claude refuses its own domains in `frameDomains`, so the claude.ai bid
  dashboard page cannot be embedded. Procore and BuildingConnected are not FP's to embed. Allowing any
  origin also removes clipboard write, camera, microphone and location from every view of the connector.
- **Views reset on reload.** A view starts from its HTML each time, so draft state must live on the server.
- **App tool limits.** 64 tools per view, 45 seconds to respond, 100,000 characters of result text, tool
  definitions under 1 MiB in total.
- **Approvals follow the tool definition.** Changing an app tool's name, title, description or schema can
  make Claude ask for approval again. Put changing values in results, not definitions.
- **First message does not carry app tools.** Claude receives a view's tools with the message after the
  view opens.
- **Custom connector URL rules (embedded sites).** Lower-case path without `%`, `;` or `//`, or the
  connector does not count as custom.
- **Side panel sizes.** Opens at about half the chat width, minimum about 320 px. The view reads
  `fullscreen` in both the panel and full screen, so lay out by container size.
- **Mobile.** Views render as inline cards. There is no side panel, camera, microphone or location.
- **Preview.** `preferredDisplayMode` and the `openai/ui` entry point key are host-specific and may change.

## Implementation pointers

- Entry point: on the tool's `_meta`, keep `ui.resourceUri` and add
  `"openai/ui": { "entrypoints": [{ "type": "global" }] }`. Every input must be optional, and the view must
  show a useful state for `{}` arguments. After changing it, use Refresh tools list on the connector.
- Side panel without a click: `_meta.ui.preferredDisplayMode: "fullscreen"` on the `ui://` resource's
  content item.
- App tools: `app.registerTool` in the view script before `app.connect()` (needs
  `@modelcontextprotocol/ext-apps` 1.7.0 or later and a Standard Schema library such as zod 4.2 or later),
  or the `onlisttools` / `oncalltool` handlers with hand-written JSON Schema.
- App-only server tools: set `_meta.ui.visibility` to `["app"]` so Claude cannot call them.
- `ui.domain` for Claude: first 32 hex characters of the SHA-256 of the server URL, followed by
  `.claudemcpcontent.com`.
- External origins are blocked by default. Declare them in `_meta.ui.csp` (`connectDomains`,
  `resourceDomains`, `frameDomains`).

## Suggested order

1. Port the staffing dashboard to a view. It is already server-built HTML and works without gated access.
2. Add an entry point, the side-panel preference and one app tool to it. That shows whether the
   organization has access.
3. Build the draft RFI editor as the first write flow.
4. Build the drawing viewer.

## Not verified

- The FP MCP server source, and therefore the claim that it has no MCP App today.
- Whether the organization has access to the side panel, entry points, app tools or embedded sites.
- Whether FP MCP has any directory listing.
- MCP Apps helper support on a Python server.
- A third-party write-up (max.nardit.com) on listing differences could not be opened from the session.

## Sources

- https://claude.com/resources/articles/interactive-connectors-full-tool
- https://claude.com/docs/connectors/building/mcp-apps/getting-started.md
- https://claude.com/docs/connectors/building/mcp-apps/display-modes.md
- https://claude.com/docs/connectors/building/mcp-apps/entry-points
- https://claude.com/docs/connectors/building/mcp-apps/app-tools
- https://claude.com/docs/connectors/building/mcp-apps/send-messages.md
- https://claude.com/docs/connectors/building/mcp-apps/download-files.md
- https://claude.com/docs/connectors/building/mcp-apps/embedded-sites
- https://claude.com/docs/connectors/building/mcp-apps/design-guidelines.md
- https://claude.com/docs/connectors/verification.md
- https://techinformed.com/anthropic-brings-interactive-workplace-tools-into-claude-via-mcp-apps/
