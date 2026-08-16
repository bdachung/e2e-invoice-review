# Live document-processing progress

## Outcome

Each document run publishes live, best-effort pipeline progress over a WebSocket.
The browser uses it to show classification, extraction, normalization, validation,
and GL-suggestion progress. `GET /api/documents/{id}` remains the fallback and
source of the final persisted result.

## Why

Azure processing can take long enough that a static spinner gives no useful
feedback. A WebSocket makes the existing background-task orchestration visible
without adding a queue, worker, or dependency.

## Endpoint

```text
ws://127.0.0.1:8000/api/documents/{document_id}/progress
```

Events are JSON objects with `document_id`, `step`, `status`, and an optional
`message`. `status` is `started`, `completed`, or `failed`. A terminal event has
no step and signals that the frontend should refresh the normal document endpoint.

## Checkpoint

- [ ] Uploading a document returns `202 Accepted` and opens a progress socket.
- [ ] The processing screen marks each pipeline step complete as it finishes.
- [ ] If the socket reconnects, the broker replays events collected for that run.
- [ ] The final review is still retrieved from `GET /api/documents/{id}`.
