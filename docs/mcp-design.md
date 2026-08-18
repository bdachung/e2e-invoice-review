# Northstar Finance MCP Server — Technical Design

## 1. Purpose

This document defines the technical design for the **MCP server only**.

The existing Northstar finance application server already exists and remains the source of truth for:

- document extraction
- invoice / receipt classification
- field validation
- EU VAT format validation
- subtotal / VAT / total reconciliation
- duplicate detection
- purchase-order matching
- GL-account suggestion
- approval / rejection state
- supplier-email draft generation
- review history

The MCP server does **not** reimplement those capabilities.

Its purpose is to expose selected finance capabilities to an AI chatbot through the Model Context Protocol (MCP).

The expected user experience is:

1. The user uploads an invoice or receipt in the chat application.
2. The chat host obtains a reference to that document.
3. The AI calls the MCP `process_document` tool.
4. The MCP server reports processing progress.
5. The MCP server returns the final finance-review result.
6. The chatbot displays the result.
7. The user can explicitly choose:
   - **Approve**
   - **Reject**
   - **Draft Email**

---

## 2. Scope

### 2.1 In scope

The MCP server will:

- expose finance capabilities as MCP tools
- call the existing application logic through a thin adapter
- return structured tool results
- expose a long-running document-processing tool
- report progress while document processing is running
- expose explicit human-triggered approval and rejection tools
- expose a supplier-correction email drafting tool
- preserve the existing finance application's business rules
- provide a clean interface that can be used by an MCP-compatible AI client

### 2.2 Out of scope

The MCP server will **not** define or replace:

- the existing application server
- file-storage architecture
- database schema
- OCR / VLM implementation
- VAT-validation implementation
- duplicate-detection implementation
- PO-matching implementation
- GL-classification implementation
- review-history implementation
- authentication architecture of the existing application
- the frontend upload implementation

The MCP server is an **adapter layer**, not a second finance backend.

---

## 3. Core Design Principle

The finance application owns the business logic.

The MCP server exposes that logic to AI clients.

```text
                    MCP Client / AI Agent
                             |
                             | MCP
                             v
                    +------------------+
                    | Finance MCP      |
                    | Server           |
                    +--------+---------+
                             |
                             | thin adapter
                             v
                    +------------------+
                    | Existing Finance |
                    | Application      |
                    | Capabilities     |
                    +------------------+
```

The MCP layer should contain as little domain logic as possible.

For example:

```python
@mcp.tool()
async def approve_document(review_id: str, reviewer_id: str):
    return await finance_adapter.approve_document(
        review_id=review_id,
        reviewer_id=reviewer_id,
    )
```

The MCP tool should **not** duplicate approval logic.

---

## 4. Integration Boundary

The MCP server should depend on one internal abstraction such as:

```python
class FinanceAdapter:
    async def process_document(self, document_ref: str): ...
    async def approve_document(self, review_id: str, reviewer_id: str): ...
    async def reject_document(
        self,
        review_id: str,
        reviewer_id: str,
        reason: str,
    ): ...
    async def draft_supplier_email(self, review_id: str): ...
```

How `FinanceAdapter` reaches the existing application is deliberately outside this document.

Possible implementations include:

### Same Python codebase

```text
MCP tool
   |
   v
FinanceAdapter
   |
   v
existing Python services
```

### Existing application is a separate service

```text
MCP tool
   |
   v
FinanceAdapter
   |
   v
existing application API / SDK
```

The MCP interface should remain the same in either case.

---

# 5. MCP Tool Surface

V1 should expose **four business-level tools**.

```text
1. process_document
2. approve_document
3. reject_document
4. draft_supplier_email
```

This is intentionally coarse-grained.

The MCP server should **not** expose low-level tools such as:

```text
extract_supplier()
extract_total()
validate_vat()
check_subtotal()
check_tax()
```

Those operations already belong to the finance application.

A small tool surface makes tool selection easier for the agent and keeps orchestration logic inside the finance domain layer.

---

# 6. Tool 1 — `process_document`

## 6.1 Purpose

Process one uploaded invoice or receipt from beginning to end and return the final finance-review result.

This is the primary MCP tool used by the chatbot.

### Input

```json
{
  "document_ref": "doc_123"
}
```

`document_ref` is an opaque reference supplied by the host application.

The MCP server does not need to know how the file was uploaded or stored.

---

## 6.2 Expected internal flow

Conceptually:

```text
process_document(document_ref)
        |
        v
Load document
        |
        v
Classify
Invoice / Receipt
        |
        v
Extract fields
        |
        v
Apply deterministic document policy
        |
        +--> Required fields
        +--> VAT format
        +--> Totals reconciliation
        +--> Duplicate detection
        +--> PO matching when applicable
        |
        v
Suggest GL account
        |
        v
Generate final conclusion
        |
        v
Persist / obtain review_id
        |
        v
Return ReviewResult
```

The MCP server itself should call one existing orchestration function if that function already exists.

For example:

```python
result = await finance_adapter.process_document(document_ref)
```

If the existing application exposes individual processing stages, the MCP adapter may coordinate them, but domain policies should remain inside the application layer.

---

## 6.3 Suggested result

```json
{
  "review_id": "review_91a8",
  "document_ref": "doc_123",
  "document_type": "invoice",
  "status": "needs_review",
  "fields": {
    "supplier_name": "ABC GmbH",
    "supplier_vat_id": "DE123456789",
    "customer_name": "Northstar Ltd",
    "invoice_number": "INV-2026-001",
    "purchase_order": "PO-10021",
    "currency": "EUR",
    "subtotal": 1000.0,
    "vat": 200.0,
    "total": 1200.0
  },
  "validation": {
    "vat_format": "pass",
    "totals": "pass",
    "duplicate": "pass",
    "po_match": "warning"
  },
  "gl_suggestion": {
    "code": "6300",
    "name": "Software"
  },
  "conclusion": "The invoice requires review because its total differs from the referenced purchase order.",
  "allowed_actions": [
    "approve",
    "reject",
    "draft_email"
  ]
}
```

The exact schema can follow the models already used by the existing application.

The important requirement is that the MCP tool returns a **structured result**, not only free-form text.

---

# 7. Streaming Progress for `process_document`

`process_document` may take several seconds because it can include:

- file parsing
- model inference
- validation
- duplicate lookup
- PO matching
- GL suggestion

The chatbot should therefore show progress while the tool is running.

Example user experience:

```text
Analyzing document...

✓ Document classified as invoice
✓ Fields extracted
✓ VAT format validated
✓ Totals reconciled
✓ Duplicate check completed
→ Matching purchase order...
→ Suggesting GL account...
```

---

## 7.1 MCP progress messages

With the MCP Python SDK, a tool can receive an injected `Context` and report progress.

Conceptually:

```python
@mcp.tool()
async def process_document(document_ref: str, ctx: Context) -> dict:
    await ctx.report_progress(1, 7, "Classifying document")
    ...
    await ctx.report_progress(2, 7, "Extracting document fields")
    ...
    await ctx.report_progress(3, 7, "Validating document")
    ...
    await ctx.report_progress(4, 7, "Checking duplicates")
    ...
    await ctx.report_progress(5, 7, "Matching purchase order")
    ...
    await ctx.report_progress(6, 7, "Suggesting GL account")
    ...
    await ctx.report_progress(7, 7, "Review complete")
    return result
```

The exact progress stages should reflect the functions already available in the finance application.

---

## 7.2 Streamable HTTP

For a remotely deployed MCP server, use **Streamable HTTP**.

Conceptually:

```text
MCP Client                         MCP Server

     tools/call
     process_document
-------------------------------------->

<---------- progress -----------------
          Classifying document

<---------- progress -----------------
          Extracting fields

<---------- progress -----------------
          Validating totals

<---------- progress -----------------
          Checking duplicates

<---------- progress -----------------
          Matching PO

<---------- progress -----------------
          Suggesting GL account

<---------- final tool result --------
          ReviewResult
```

The application should use the MCP SDK's progress mechanism instead of manually defining an SSE protocol.

The transport is responsible for carrying the MCP progress notifications.

### Important configuration note

If per-request progress messages are required, avoid configuring the Streamable HTTP endpoint to force every request into a single JSON response.

The current MCP Python SDK documents that `json_response=True` returns a single JSON body and drops in-flight progress notifications for that request.

For `process_document`, use the Streamable HTTP response stream.

---

# 8. Tool 2 — `approve_document`

## Purpose

Approve an already processed finance review.

### Input

```json
{
  "review_id": "review_91a8",
  "reviewer_id": "maya"
}
```

### Suggested result

```json
{
  "review_id": "review_91a8",
  "status": "approved",
  "reviewer_id": "maya"
}
```

## Human-control requirement

The LLM must **not autonomously decide to call this tool**.

Expected flow:

```text
AI:
The document passed all validations.

Suggested action:
Approve

        |
        v

UI:
[ Approve ]

        |
        | explicit human click
        v

approve_document(...)
```

The AI may recommend an action.

The human reviewer owns the financial decision.

---

# 9. Tool 3 — `reject_document`

## Purpose

Reject an already processed document.

### Input

```json
{
  "review_id": "review_91a8",
  "reviewer_id": "maya",
  "reason": "Invoice amount does not match the purchase order."
}
```

### Suggested result

```json
{
  "review_id": "review_91a8",
  "status": "rejected",
  "reason": "Invoice amount does not match the purchase order."
}
```

## Expected flow

```text
UI:
[ Reject ]

     |
     v

Enter rejection reason

     |
     v

reject_document(
    review_id,
    reviewer_id,
    reason
)
```

Like approval, rejection should be triggered only by an explicit reviewer action.

---

# 10. Tool 4 — `draft_supplier_email`

## Purpose

Generate a supplier-correction email based on:

- extracted supplier information
- invoice / receipt identifier
- detected validation issues
- PO mismatch
- rejection reason
- corrected reviewer values when available

### Input

```json
{
  "review_id": "review_91a8"
}
```

Optional:

```json
{
  "review_id": "review_91a8",
  "reason": "Please correct the purchase-order amount."
}
```

### Suggested result

```json
{
  "subject": "Correction required for Invoice INV-2026-001",
  "body": "Dear ABC GmbH,\n\nWe identified a discrepancy..."
}
```

## Important restriction

This tool only **drafts** an email.

It must not expose:

```text
send_email()
```

The generated text is returned to the chat UI for review, editing, or copying.

---

# 11. Expected Chat Flow

The MCP server should support the following interaction.

```text
User
 |
 | uploads invoice.pdf
 v
Chat Host
 |
 | receives document_ref
 v
AI Agent
 |
 | calls process_document(document_ref)
 v
MCP Server
 |
 | progress notifications
 |
 | final ReviewResult
 v
AI Agent
 |
 | formats result
 v
Chat UI
```

Example final chat response:

```text
Review complete.

Document type: Invoice
Supplier: ABC GmbH
Invoice: INV-2026-001
Total: EUR 1,200.00

✓ VAT format
✓ Totals reconciliation
✓ Duplicate check
⚠ Purchase-order matching

Suggested GL:
6300 — Software

Conclusion:
The invoice requires review because the total differs
from the referenced purchase order.

[ Approve ]   [ Reject ]   [ Draft Email ]
```

---

# 12. Action Flow

After `process_document`, the returned `review_id` becomes the stable identifier for subsequent MCP calls.

```text
                 process_document
                        |
                        v
                  review_91a8
                        |
          +-------------+-------------+
          |             |             |
          v             v             v
       Approve        Reject       Draft Email
          |             |             |
          v             v             v
 approve_document  reject_document  draft_supplier_email
```

This is preferable to repeatedly passing all extracted invoice fields between tools.

The existing application remains responsible for storing the authoritative review state.

---

# 13. Suggested MCP Server Structure

```text
mcp_server/
├── __init__.py
├── server.py
├── adapter.py
├── tools/
│   ├── __init__.py
│   ├── processing.py
│   ├── review.py
│   └── email.py
└── schemas/
    ├── __init__.py
    └── results.py
```

### `server.py`

Responsible for:

- creating the MCP server
- registering tools
- selecting the MCP transport
- starting the server

### `adapter.py`

Responsible for:

- accessing the existing finance application
- hiding implementation details from MCP tools
- translating application results into MCP result schemas

### `tools/`

Responsible only for:

- MCP tool definitions
- MCP descriptions
- argument validation
- progress reporting
- calling `FinanceAdapter`

### `schemas/`

Optional MCP-facing response models.

Prefer reusing existing application models when possible.

---

# 14. Example Server Skeleton

The following is illustrative; adapt imports to the exact MCP SDK version pinned by the project.

```python
from mcp.server.mcpserver import Context, MCPServer

from .adapter import FinanceAdapter

mcp = MCPServer("Northstar Finance")
finance = FinanceAdapter()


@mcp.tool()
async def process_document(
    document_ref: str,
    ctx: Context,
) -> dict:
    """Process an invoice or receipt and return its finance review."""

    async def progress(step: int, total: int, message: str):
        await ctx.report_progress(step, total, message)

    return await finance.process_document(
        document_ref=document_ref,
        progress_callback=progress,
    )


@mcp.tool()
async def approve_document(
    review_id: str,
    reviewer_id: str,
) -> dict:
    """Approve a reviewed finance document after explicit human action."""

    return await finance.approve_document(
        review_id=review_id,
        reviewer_id=reviewer_id,
    )


@mcp.tool()
async def reject_document(
    review_id: str,
    reviewer_id: str,
    reason: str,
) -> dict:
    """Reject a reviewed finance document after explicit human action."""

    return await finance.reject_document(
        review_id=review_id,
        reviewer_id=reviewer_id,
        reason=reason,
    )


@mcp.tool()
async def draft_supplier_email(
    review_id: str,
    reason: str | None = None,
) -> dict:
    """Draft, but never send, a supplier correction email."""

    return await finance.draft_supplier_email(
        review_id=review_id,
        reason=reason,
    )


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        stateless_http=True,
    )
```

For local development, the same server can also be exposed through `stdio`.

---

# 15. Tool Descriptions Matter

The model uses tool metadata to decide which tool to call.

Descriptions should therefore clearly define the intended action.

Good:

```text
process_document:
Process one uploaded invoice or receipt through the existing
Northstar finance review workflow and return the complete review.
```

Bad:

```text
process_document:
Processes stuff.
```

Good:

```text
approve_document:
Approve an existing finance review. Call this tool only after
an explicit reviewer approval action.
```

This is especially important for the approval and rejection tools.

---

# 16. Error Handling

MCP tool errors should be structured and understandable by the agent.

Examples:

### Unknown document

```json
{
  "error": "DOCUMENT_NOT_FOUND",
  "message": "The document reference does not exist."
}
```

### Processing failed

```json
{
  "error": "DOCUMENT_PROCESSING_FAILED",
  "message": "The document could not be processed."
}
```

### Missing PO

This should normally be a **review warning**, not an MCP transport error:

```json
{
  "po_match": "not_available",
  "message": "No purchase order was found."
}
```

### Invalid review state

```json
{
  "error": "INVALID_REVIEW_STATE",
  "message": "An approved review cannot be rejected."
}
```

The MCP server should preserve the semantics already defined by the finance application.

---

# 17. Authorization Boundary

The MCP server must not trust the LLM to provide authorization.

For example, this is unsafe:

```text
LLM says:
reviewer_id = "admin"
```

The trusted host or MCP client should provide reviewer identity.

Approval flow:

```text
Authenticated user
       |
       v
Chat UI
       |
       | Approve click
       v
Trusted controller
       |
       | reviewer identity
       v
MCP approve_document
```

At minimum, the server should ensure:

- a valid user is associated with human actions
- approval / rejection permissions are checked
- review state transitions are validated
- tool calls are audit logged
- sensitive document information is not unnecessarily returned

---

# 18. Observability

For each MCP tool call, log at least:

```text
request_id
tool_name
document_ref / review_id
actor when applicable
start_time
end_time
latency
status
error
```

For `process_document`, also consider recording stage-level timing:

```text
classification_ms
extraction_ms
validation_ms
duplicate_check_ms
po_matching_ms
gl_suggestion_ms
```

This will make it easier to debug slow tool calls and demonstrate production-oriented MCP engineering.

---

# 19. Testing Strategy

## 19.1 Tool contract tests

Test:

```text
process_document
approve_document
reject_document
draft_supplier_email
```

with a mocked `FinanceAdapter`.

The purpose is to verify that MCP arguments and outputs remain stable independently of the finance implementation.

## 19.2 Integration tests

Run the MCP server against the existing finance application and test representative cases.

### Invoice — clean

```text
Expected:
all validation PASS
```

### Invoice — PO mismatch

```text
Expected:
process succeeds
po_match = WARNING / FAIL
human review required
```

### Receipt

```text
Expected:
receipt policy applied
no unnecessary PO requirement
```

### Duplicate

```text
Expected:
possible duplicate warning
```

### Approval

```text
Expected:
only explicit approve tool changes status
```

### Rejection

```text
Expected:
reason persisted
```

### Draft email

```text
Expected:
text generated
no external email is sent
```

## 19.3 Progress-streaming test

Verify that `process_document` produces ordered progress events before its final result.

Expected example:

```text
1. Classifying document
2. Extracting fields
3. Validating document
4. Checking duplicates
5. Matching purchase order
6. Suggesting GL account
7. Review complete
8. Final tool result
```

---

# 20. Acceptance Criteria

The MCP implementation is complete when:

- [ ] The MCP server starts independently.
- [ ] An MCP client can discover the four finance tools.
- [ ] `process_document` accepts a document reference.
- [ ] `process_document` reuses existing finance functionality.
- [ ] Processing progress can be observed by an MCP client.
- [ ] The final result contains a stable `review_id`.
- [ ] Approve can only occur through the explicit approval tool.
- [ ] Reject can only occur through the explicit rejection tool.
- [ ] Rejection supports a reason.
- [ ] Draft Email returns editable text.
- [ ] Draft Email cannot send an email.
- [ ] The MCP layer contains no duplicated finance policy.
- [ ] Errors are returned in a predictable form.
- [ ] MCP tool calls are traceable in logs.
- [ ] The server can be tested locally through an MCP development client / Inspector.
- [ ] The deployed server can run using Streamable HTTP.

---

# 21. Recommended Implementation Order

## Step 1 — MCP skeleton

Implement:

```text
MCPServer
+
dummy process_document
```

Verify tool discovery.

## Step 2 — Finance adapter

Create:

```python
FinanceAdapter
```

Connect it to the already existing finance application.

## Step 3 — `process_document`

Return the real finance review result.

Do not add streaming yet.

## Step 4 — Add progress reporting

Add `Context.report_progress()` to the long-running workflow.

Verify progress from an MCP client.

## Step 5 — Human actions

Implement:

```text
approve_document
reject_document
```

Ensure they require explicit application-side user actions.

## Step 6 — Draft email

Implement:

```text
draft_supplier_email
```

Confirm there is no send-email capability.

## Step 7 — Hardening

Add:

```text
authorization
audit logging
error mapping
tests
latency tracing
```

---

# 22. Final MCP Server Flow

```text
                        +----------------------+
                        |     MCP Client       |
                        |      / Agent         |
                        +----------+-----------+
                                   |
                                   | process_document
                                   v
                        +----------------------+
                        | Northstar Finance    |
                        | MCP Server           |
                        +----------+-----------+
                                   |
                                   | FinanceAdapter
                                   v
                        +----------------------+
                        | Existing Finance     |
                        | Application          |
                        +----------+-----------+
                                   |
                         existing business logic
                                   |
                                   v
                              ReviewResult
                                   |
             progress <------------+------------> final result
                                   |
                                   v
                        +----------------------+
                        | Chat Result          |
                        |                      |
                        | [Approve]            |
                        | [Reject]             |
                        | [Draft Email]        |
                        +----+--------+--------+
                             |        |
                    explicit human actions
                             |        |
                 +-----------+        +----------------+
                 v                                     v
       approve_document /                    draft_supplier_email
       reject_document
```

---

# 23. Design Summary

The MCP server should be a **thin, safe, business-level adapter** around the existing finance application.

The V1 MCP contract is intentionally small:

```text
process_document
approve_document
reject_document
draft_supplier_email
```

The most important architectural decisions are:

1. **Do not duplicate existing finance logic in the MCP server.**
2. **Use a document reference rather than making MCP responsible for file upload.**
3. **Use a stable `review_id` for all post-processing actions.**
4. **Use MCP progress notifications for long-running document processing.**
5. **Use Streamable HTTP for remote deployment.**
6. **Keep Approve and Reject behind explicit human actions.**
7. **Draft supplier emails, but never send them automatically.**

This keeps the MCP implementation small enough for a personal project while still demonstrating:

- MCP server development
- business-level tool design
- agent integration
- Streamable HTTP
- progress notifications
- human-in-the-loop control
- production-oriented error handling
- observability
- integration with an existing real application

---

## References

- MCP Python SDK v2 documentation: https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/index.md
- Running MCP servers and transports: https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/run/index.md
- MCP handler context and progress reporting: https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/handlers/context.md
- Streaming example: https://github.com/modelcontextprotocol/python-sdk/blob/main/examples/stories/streaming/server.py
