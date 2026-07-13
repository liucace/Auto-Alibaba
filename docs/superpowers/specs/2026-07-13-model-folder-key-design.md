# Model Folder Key Design

## Goal

Allow a product whose complete business model is `W3G800-KS39-03/F01` to use the Windows-safe local folder name `W3G800-KS39-03F01` without changing the model stored in inventory, prepared JSON, task state, browser fields, or upload results.

## Design

Introduce one model-to-folder-key function in the model-number module. It first applies the existing model normalization and then removes `/` only for local directory lookup. Business comparisons continue to use the existing normalized model and therefore preserve the slash.

Use the folder key consistently for both product source directories under `data/<lifecycle>/` and prepared artifact directories under `automation/`. Do not add fallback copies, aliases, nested directories, or fuzzy matching.

## Data Flow

1. Accept the exact requested model `W3G800-KS39-03/F01`.
2. Normalize it as a business model without deleting `/`.
3. Derive the local folder key `W3G800-KS39-03F01` only when constructing filesystem paths.
4. Validate inventory and every prepared JSON model against the original normalized business model.
5. Send the original normalized business model to the 1688 form and task state.

## Error Handling

Missing source folders or prepared artifacts remain hard preflight failures. No missing parameters or artifacts may be generated during upload. Existing containment and main-image size checks remain unchanged.

## Tests

Add regression coverage proving that:

- the folder key removes `/` while ordinary model normalization preserves it;
- source lookup finds `data/<lifecycle>/W3G800-KS39-03F01` for `W3G800-KS39-03/F01`;
- prepared artifact lookup uses `automation/W3G800-KS39-03F01` while exact JSON model validation still requires `W3G800-KS39-03/F01`.

After implementation, run focused unit tests, the full test suite, the uploader preflight, and then the approved upload entry point. The upload must still stop before clicking “保存草稿”.
