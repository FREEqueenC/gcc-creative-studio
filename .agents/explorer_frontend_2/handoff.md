# Frontend Scan Report (handoff.md)

## 1. Observation

### Scan Execution & Tool Output
The frontend repository (`C:\Users\Ashle\Documents\GitHub\gcc-creative-studio\frontend`) was examined using the following local tools and commands:
- **Search Command for TODOs / placeholders:** `Get-ChildItem -Path "frontend\src" -Recurse -File | Select-String -Pattern "TODO|FIXME|HACK"`
  - *Result output snippet:*
    ```
    C:\Users\Ashle\Documents\GitHub\gcc-creative-studio\frontend\src\app\admin\media-templates-management\media-templates-management.component.ts:119: // TODO: Replace with actual service call
    C:\Users\Ashle\Documents\GitHub\gcc-creative-studio\frontend\src\app\admin\media-templates-management\media-templates-management.component.ts:129: // TODO: Add snackbar for user feedback
    C:\Users\Ashle\Documents\GitHub\gcc-creative-studio\frontend\src\app\admin\media-templates-management\media-templates-management.component.ts:136: // TODO: Add snackbar for user feedback
    C:\Users\Ashle\Documents\GitHub\gcc-creative-studio\frontend\src\app\common\models\generated-image.model.ts:17: // TODO: Check if this file is neccessary with the latest refactoring
    C:\Users\Ashle\Documents\GitHub\gcc-creative-studio\frontend\src\app\video\video.component.ts:758: // TODO: Add notification when video is completed after the pooling
    C:\Users\Ashle\Documents\GitHub\gcc-creative-studio\frontend\src\app\workflows\workflow.service.ts:106: // TODO: If we are selecting a workflow run we should query another endpoint
    C:\Users\Ashle\Documents\GitHub\gcc-creative-studio\frontend\src\app\workflows\workflow-editor\workflow-editor.component.html:165: <!-- TODO: Add tabs if a step has multiple output types -->
    C:\Users\Ashle\Documents\GitHub\gcc-creative-studio\frontend\src\app\workflows\workflow-editor\workflow-editor.component.ts:168: // TODO: Create and use a WorkflowRunService
    ```
- **Prettier Format Audit Command:** `npm run check-format`
  - *Result:* Output exit code 1; flagged 285 files with warnings:
    ```
    Checking formatting...
    [warn] src/app/admin/admin-auth.guard.spec.ts
    ...
    [warn] Code style issues found in 285 files. Run Prettier with --write to fix.
    ```
- **TypeScript Compilation Command:** `npm run compile` (`tsc --noEmit`)
  - *Result:* Completed successfully with no stdout/stderr output (clean compilation).
- **GTS Linting Command:** `npm run lint` (`gts lint`)
  - *Result:* Output exit code 1; flagged 26,963 formatting problems, primarily:
    ```
    error    Delete `␍`    prettier/prettier
    warning  Strings must use singlequote   quotes
    ```

---

## 2. Logic Chain

1. **Prettier Check Warnings (CRLF vs LF Line Endings):** Prettier checks on Windows default-checkouts failed for 285 files. The error `Delete ␍` indicates the repository files contain Windows-style Carriage Returns (`\r\n` or CRLF). Standard linting expectations specify Unix-style Line Feed endings (`\n` or LF).
2. **Double Quotes warnings:** GTS lint flagged string errors in `environment.ts` and `environment.development.ts` because Firebase configurations use double quotes (`"`) instead of single quotes (`'`), violating GTS standard guidelines.
3. **Broken Workflow Run Details Functionality:**
   - `workflow-editor.component.ts` line 168 maps a route with `runId` to `of(null)`.
   - The route param subscription extracts `this.runId`. But `app-routing.module.ts` defines no route containing a `:runId` parameter. Thus, `runId` is always null, and the route mapping code is dead and functionally broken.
4. **Silent Exception in Batch Execution:**
   - In `execution-history.component.ts` at lines 149-152, the method `openBatchExecution` subscribes to `getWorkflowById` without registering an error handler:
     ```ts
     this.workflowService.getWorkflowById(this.workflowId).subscribe(wf => {
       this.workflow = wf;
       this.openBatchDialog();
     });
     ```
   - If the backend fails or returns an HTTP error, the subscription will throw an unhandled exception, causing the UI to freeze silently without warning the user.
5. **Copy-paste Snackbar Labeling Bugs:**
   - In `video.component.ts` line 772, VEO video generation errors are handled using the label `'Search'`.
   - In `home.component.ts` line 804, Imagen image generation errors are handled using the label `'Search'`.
   - This occurs due to copy-pasting subscription error blocks from the Search component without modifying the error context argument.

---

## 3. Caveats

- **Backend Integration:** This scan is strictly frontend-centric and read-only. I assumed the backend endpoints (e.g. `/api/workflows/:id/executions`) are fully operational and behave according to the typescript model contracts.
- **External Sign-in Setup:** The Google One Tap integration requires a valid client ID and correct DNS configuration in the Google Cloud Console. I could not verify if the One Tap prompt works locally in development without these setups.

---

## 4. Conclusion

Below is the comprehensive list of identified placeholders, stubs, formatting errors, and broken code:

| File Path & Line Number | Issue Type | Brief Description of the Issue | Actionable Fix / Recommended Replacement |
| :--- | :--- | :--- | :--- |
| `src/app/workflows/workflow-editor/workflow-editor.component.ts` <br> Line 168-170 | **Broken Code / Placeholder** | The editor returns `of(null)` when fetching a workflow run by ID. This leaves the form blank/empty. | Create `WorkflowRunService` or implement `getWorkflowRun` within `WorkflowService`, and replace `of(null)` with `this.workflowService.getWorkflowRun(this.runId)`. |
| `src/app/app-routing.module.ts` <br> Line 83-101 | **Broken Code** | Missing route definition for viewing a workflow run (`workflows/run/:runId` or similar). | Add `{ path: 'run/:runId', component: WorkflowEditorComponent, canActivate: [AuthGuardService] }` under `workflows` children routes. |
| `src/app/workflows/execution-history/execution-history.component.ts` <br> Line 149-152 | **Broken Code** | Missing error handler in `getWorkflowById` subscription before opening batch dialogue. | Replace with:<br>`this.workflowService.getWorkflowById(this.workflowId).subscribe({ next: wf => { this.workflow = wf; this.openBatchDialog(); }, error: err => handleErrorSnackbar(this.snackBar, err, 'Fetch workflow') });` |
| `src/app/video/video.component.ts` <br> Line 772 | **Broken Code** | Copy-paste error: VEO generation error snackbar is labeled `'Search'` instead of `'VEO Video Generation'`. | Replace `'Search'` with `'VEO Video Generation'`. |
| `src/app/home/home.component.ts` <br> Line 804 | **Broken Code** | Copy-paste error: Imagen generation error snackbar is labeled `'Search'` instead of `'Imagen Generation'`. | Replace `'Search'` with `'Imagen Generation'`. |
| `src/app/admin/media-templates-management/media-templates-management.component.ts` <br> Line 119-122 | **Placeholder / Stub** | Comment `// TODO: Replace with actual service call` is obsolete since the service call is active. | Remove obsolete commented-out lines (119-122). |
| `src/app/admin/media-templates-management/media-templates-management.component.ts` <br> Line 129, 136 | **Placeholder / Stub** | Stubs `// TODO: Add snackbar for user feedback` where notifications are completely missing. | Call `handleSuccessSnackbar` (line 129) and `handleErrorSnackbar` (line 136). |
| `src/environments/environment.prod.ts` <br> Line 32 | **Placeholder / Stub** | Google OAuth client ID is set to `'GOOGLE_CLIENT_ID_PLACEHOLDER'`. | Replace with the actual Google Cloud Console Client ID. |
| `src/environments/environment.ts` <br> Line 32 | **Placeholder / Stub** | Google OAuth client ID is empty `''`. | Replace with the actual Google Cloud Console Client ID. |
| `src/environments/environment.development.ts` <br> Line 12 | **Placeholder / Stub** | Google OAuth client ID is empty `""`. | Replace with the actual Google Cloud Console Client ID. |
| `src/index.html` <br> Line 53 | **Placeholder / Stub** | Hardcoded reCAPTCHA enterprise site key `6LeRPkAtAAAAAKnaiVVAsifsZcq2mSi6Zi_yKlLe`. | Move to environment files or keep if designated for all environments. |
| **All repository files** <br> (285 files) | **Formatting** | Prettier check fails due to CRLF (`\r\n`) line endings instead of Unix LF endings. | 1. Add `.prettierrc` with `{"endOfLine": "auto"}`.<br>2. Add `.gitattributes` with `* text eol=lf`. |
| `src/environments/environment.ts` <br> Lines 19-24 <br> `src/environments/environment.development.ts` <br> Lines 3-8 | **Formatting** | Double quotes used instead of single quotes for Firebase configuration values. | Replace double quotes `"` with single quotes `'` (e.g. `apiKey: 'AIza...'`). |
| `src/app/common/models/generated-image.model.ts` <br> Line 17 | **Placeholder / Stub** | `// TODO: Check if this file is neccessary with the latest refactoring`. | Check references. If unused, delete the file; if used, remove the TODO comment. |
| `src/app/video/video.component.ts` <br> Line 758 | **Placeholder / Stub** | `// TODO: Add notification when video is completed after the pooling`. | Implement completed notification triggers using `handleSuccessSnackbar`. |
| `src/app/workflows/workflow.service.ts` <br> Line 106 | **Placeholder / Stub** | `// TODO: If we are selecting a workflow run we should query another endpoint`. | Update the endpoint inside `getWorkflowById` if it represents a workflow run. |
| `src/app/workflows/workflow-editor/workflow-editor.component.html` <br> Line 165 | **Placeholder / Stub** | `<!-- TODO: Add tabs if a step has multiple output types -->`. | Implement output tab sections when multiple outputs exist. |

---

## 5. Verification Method

To verify these findings and check code changes:
1. **Formatting verification:** Run `npm run check-format` inside `frontend/` to view formatting violations.
2. **Compilation verification:** Run `npm run compile` to verify that there are no syntax or type errors in the TypeScript compiler.
3. **Linting verification:** Run `npm run lint` to review GTS rule violations.
4. **Behavioral check:** Navigate to the `/workflows/edit/:id` route vs trying to access `/workflows/run/:id` in browser devtools to verify routing/navigation errors.
