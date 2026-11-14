# DataSoft Service Request Portal — QFD General Requirements

> Plain-text copy of `DataSoft_QFD_General_Requirements5 (3).docx` (repository root) so agents can read it. The .docx is the original; regenerate this file if it changes.

## 1. Problem Description and Current Manual Process

### 1.1 Current Situation (As-Is)

DataSoft currently handles client service requests mainly through email. A bank employee submits an issue for internal approval before it is sent to DataSoft. DataSoft then reviews the request, accepts or rejects it, assigns staff when available, and delivers the completed work. Screenshots, clarifications, delivery dates, and progress updates can become scattered across separate email conversations. Checking the status of a request or compiling a service history often requires searching through those messages.

### 1.2 Example of the Current Process

For example, a bank employee might receive an error after confirming a fund transfer with an OTP. The following steps show how a request of this kind could be handled through email.

Problem discovered at the client: The bank employee encounters the error, notes the affected screen and software version (if known), and captures an error message or screenshot.

Issue prepared in email: The employee writes a message explaining what happened, when it happened, and how to reproduce it. Important information may be omitted because there is no standardized request form.

Internal client approval by email: The message is forwarded to a responsible official. The official may approve it, request revisions, or decline to forward it. The decision may be recorded only in the email chain.

Request emailed to DataSoft: Once approved, the bank sends the request to a DataSoft contact or service mailbox. Different contacts and email subjects can create separate threads for the same problem.

DataSoft reviews the message: A DataSoft employee reads the email, asks follow-up questions if needed, and replies that the request is accepted or rejected, possibly with a reason. No single structured record necessarily captures the full decision sequence.

Work waits for staff availability: If accepted, the request may wait until a developer or support employee is available. The bank must ask for updates if there is no accessible shared status.

Investigation and correction: A developer investigates, changes code or configuration, and communicates progress internally. Relevant work, attachments, tests, and decisions may be spread across personal notes, Git, chat, and email.

Internal testing: DataSoft tests the changes before delivery, but the results may be stored separately from the original request.

Fix delivered to the client: DataSoft communicates the fix by email, potentially referencing a new software build, installation action, or delivery note.

Client-side checking: After delivery, a client employee may check whether the fix works in the bank's environment. The proposed portal assigns this decision to an authorized Issue Verifier.

If the problem remains: The bank replies to the email with an explanation or new screenshot. The earlier request may be reopened informally or a new email thread started, making repeated work harder to trace.

If the fix works: The bank communicates acceptance, or the parties treat the matter as complete. Later, reconstructing who confirmed what and when may require searching archived correspondence.

Other possible outcomes: The bank approver may ask for more information or reject the original request. DataSoft may also reject an approved request with a reason. If a delivered fix does not resolve the issue, it may need further work and another delivery.

### 1.3 Problems Identified

- **P-01** — Request details are scattered among email threads.  Consequence: Information is lost, repeated, or hard to retrieve.
- **P-02** — Client approval is handled informally.  Consequence: Requests can be delayed and approval responsibility becomes unclear.
- **P-03** — There is no shared structured status history.  Consequence: Clients and DataSoft repeatedly ask what stage a request has reached.
- **P-04** — Acceptance, rejection, delivery, and verification are not consistently recorded together.  Consequence: Decisions and evidence are difficult to audit or explain.
- **P-05** — Similar or recurring requests are hard to recognize.  Consequence: Employees may investigate the same or nearly identical problem repeatedly, and a problem that returns is not linked to its earlier request.
- **P-06** — Issues may be described with inconsistent terminology.  Consequence: Sorting, routing, filtering, and reporting become difficult.
- **P-07** — Requests and response times are counted manually.  Consequence: Dashboards and timely reports are hard to produce.
- **P-08** — Client-specific information may appear in mixed communication threads.  Consequence: Confidentiality and access-control risks increase.
- **P-09** — Delivery confirmation and failure feedback are not handled in a standardized workflow.  Consequence: A delivered fix may be mistaken for an accepted, working solution.
### 1.4 Problem Statement

DataSoft needs a central service-request portal to manage issues from submission to closure. It should record the client's authorization, DataSoft's acceptance or rejection, tentative and actual delivery dates, work progress, delivery details, client verification, closure, and any reopening in one place. The portal should also help users recognize similar or recurring requests, apply consistent issue labels, and protect each client's confidential information.

### 1.5 Service Request Workflow

Draft → Submitted (authorized by the Issue Officer) → Accepted / Rejected by DataSoft → Pending → In Progress → Delivered / Awaiting Client Verification → Verified → Closed by DataSoft.

If verification fails: Awaiting Client Verification → Verification Failed / Reopened → In Progress → Redelivered → Awaiting Client Verification.

If a closed issue returns: Closed → Reopened → In Progress → Redelivered → Awaiting Client Verification, provided it is reopened within 30 days of closure (an Administrator can change this period). After that period, the problem is reported as a new request marked as Recurring and linked to the earlier request.

When DataSoft accepts a request, it records a tentative delivery date or marks the date as “to be provided later”; the actual delivery date is recorded when the request is delivered. Delivery, verification, and closure are separate steps. A delivered request remains open until the Issue Verifier confirms that the issue is resolved, after which DataSoft closes it. If no response is received, the request stays pending verification unless a separate administrative closure rule has been agreed with the client. Authorization, intake, delivery, verification, closure, and reopening decisions are recorded separately, each with its status update date.

## 2. Quality Function Deployment (QFD)

The requirements are divided into three groups: Normal requirements for the portal's main functions, Expected requirements for security and reliable operation, and Exciting requirements for additional capabilities.

### 2.1 Normal Requirements

#### A. Accounts and Organization Management

- **N-01** — Authentication and account management: Authorized client and DataSoft users can sign in, sign out, reset passwords, and maintain basic profiles. New users sign in with the temporary username and password emailed to them (N-02), must set a new password at first sign-in, and can later change their username and password. An Administrator can deactivate accounts while preserving historical actions.
- **N-02** — Client organizations and account creation: A DataSoft Administrator registers banks or other client companies, each with an official contact email. Client accounts are created only by an Administrator, from the users and roles nominated by the client organization; the client's contact requests new users, role changes, and deactivations from DataSoft. Each new user receives a temporary username and password at their official email address. DataSoft employees are added by an Administrator in the same way. Every request belongs to exactly one client organization.
- **N-03** — Client-side roles: An Administrator can grant client users the Issue Officer role (the client's Officer / Issue Creator, who creates and authorizes requests) and the Issue Verifier role (who confirms whether a delivered fix resolves the issue). Both roles can view and comment on their own organization's requests. A user may hold both roles.
- **N-04** — DataSoft-side roles: DataSoft has two roles. A Support Agent can review, accept, or reject requests, set and revise delivery dates, assign work, update status, deliver fixes, and close or reopen requests. An Administrator can do everything a Support Agent can, and can also create and manage user accounts and client organizations.
#### B. Products and Service Requests

- **N-05** — Product register: DataSoft can record supported products and modules, and the product or module affected by each request. Where useful, the portal can also record the version deployed at each client and its version history.
- **N-06** — Request creation: An Issue Officer can create a request containing title, description, request type (bug/change/feature/support), affected product/module, urgency or priority, and attachments.
- **N-07** — Unique identifiers and drafts: Every request has a permanent, readable ID (such as SR-1024). Creators can save drafts and submit them later.
- **N-08** — Issue evidence: Bug requests include the environment, steps to reproduce, expected and actual results, and optional screenshots or logs. Fields may vary by request type.
- **N-09** — Request history: Significant changes record the user, time, and previous and new values. Clients see only the history they are permitted to access.
#### C. Client Authorization and DataSoft Intake

- **N-10** — Officer authorization and submission: The Issue Officer who creates a request also authorizes it. Submitting the request confirms the authorization, and the authorizing user and time are recorded. A submitted request goes directly to DataSoft's intake queue with the status Submitted; there is no separate client approval step.
- **N-11** — Related and recurring requests: While creating a request, the Issue Officer can reference an earlier request from the same organization. If a problem that was solved before has occurred again, the Officer marks the new request as Recurring, which attaches it to the previous ticket. Both requests show the link, DataSoft staff can open the earlier request's history and delivery record, and recurring requests are counted in reports.
- **N-12** — DataSoft intake decision: A Support Agent or Administrator can accept or reject a submitted request and record a client-visible reason for rejection. On acceptance, they record a tentative delivery date or mark it as “to be provided later”, and can revise it afterward. Every change to the date is kept in the request history and shown to the client.
- **N-13** — Staff assignment and status tracking: Accepted requests start as Pending (to do) and can be assigned or reassigned to responsible DataSoft personnel, who move them to In Progress. Each status change records its status update date, which is shown on the request and in reports.
#### D. Internal Work, Delivery, Verification, and Closure

- **N-14** — Internal work items: DataSoft staff can create and track internal tasks linked to a request. These tasks and their internal notes are hidden from clients.
- **N-15** — Internal work board: DataSoft personnel can view their tasks in a simple list or Kanban board; advanced sprint planning is outside the current scope.
- **N-16** — Delivery record: Staff record what changed, the delivery note, relevant version or deployment details, and optional supporting files before marking a request Delivered. The actual delivery date is recorded at that point and shown next to the tentative delivery date.
- **N-17** — Verifier notification: After delivery, the client's Issue Verifier receives an in-app and email alert, and the request enters Awaiting Client Verification.
- **N-18** — Verification outcome: An Issue Verifier reviews delivery notes and agreed acceptance criteria and records either Verified or Verification Failed. A failed result requires a reason and allows supporting evidence.
- **N-19** — Rework, reopening, and closure: After successful verification, a Support Agent or Administrator closes the request; only DataSoft can close a request. Failed verification reopens it for correction and redelivery. A closed request can also be reopened with a reason by the Issue Officer, the Issue Verifier, or DataSoft within 30 days of closure, a period an Administrator can change; after that period, the client creates a recurring request instead (N-11). Every delivery, verification, closure, and reopening is saved in the request history.
- **N-20** — Verification reminder: If no verification decision arrives within an agreed period, the system reminds the Issue Verifier and the assigned Support Agent. It does not silently classify the fix as verified.
#### E. Communication and Reporting

- **N-21** — Comments throughout the request: The bank and DataSoft can exchange client-visible comments on a request at every stage, from submission to closure and after reopening. Every action, such as rejecting, changing the delivery date, delivering, verifying, failing verification, closing, or reopening, allows a comment, and rejection, failed verification, and reopening require a reason. DataSoft staff can additionally leave internal-only notes, including on internal tasks.
- **N-22** — Notifications: In-app and email alerts cover account creation, submission, intake decisions, delivery date changes, comments and clarifications, delivery, verification, closure, and reopening. Failed emails are logged and retried.
- **N-23** — Search and dashboards: Clients can search and filter their own requests and view status counts. DataSoft can view authorized totals across clients, pending requests, and recent deliveries.
- **N-24** — Reports and export: Authorized users on both sides can generate Detailed and Summary reports, filtered by date range (by default, the current year), status, and bank. DataSoft users can report on all banks or selected banks; client users see only their own organization. A Detailed report lists each request with its request ID, bank and the Issue Officer who raised it, title and issue detail, current status, creation date, submission date (when DataSoft received it), tentative and actual delivery dates, last status update date, and closure date. A Summary report shows totals, such as the number of issues found in the selected year and counts by status, bank, and month, including reopened and recurring issues. Both reports can be exported.
- **N-25** — Simple deadline tracking: Requests whose tentative delivery date has passed without delivery show an overdue warning. Administrators may also set basic response due dates.
- **N-26** — Basic Git references: Internal tasks may store relevant commit or pull-request links. Automatic synchronization with the Git repository may be added.
### 2.2 Expected Requirements

#### A. Mandatory Security and Privacy

- **EX-01** — Server-side authorization: Every protected action checks the authenticated user's permissions in the backend, not only by hiding UI controls.
- **EX-02** — Client data isolation: A bank cannot view, search, report on, download, or receive notifications about another bank’s data. Only authorized DataSoft staff may access approved cross-client functions.
- **EX-03** — Internal information isolation: Client users cannot view internal tasks, internal comments, repository details, confidential logs, or staff-only time records.
- **EX-04** — Account and transport security: The portal provides secure login, password storage, session handling, and data transmission. Sensitive system credentials are kept protected. Temporary credentials are sent only to the registered email address, expire if unused within a set period, and must be changed at first sign-in.
- **EX-05** — Input and file safety: Forms are validated, rendered text is protected against injection, and file uploads are restricted and accessed through authorization checks.
#### B. Integrity, Reliability, and Usability

- **EX-06** — Immutable history: Users cannot edit or delete past authorizations, intake decisions, deliveries, verification results, closures, reopenings, or audit events. Corrections are recorded as new events.
- **EX-07** — Valid status changes: Rejected requests cannot be assigned, unsubmitted drafts do not reach DataSoft's intake queue, unverified deliveries cannot appear as verified, and only DataSoft can close a request. A closed request changes status only by being reopened.
- **EX-08** — Reliable operation: Users can continue creating and managing requests if the duplicate-detection or label-suggestion service is unavailable. System errors are recorded without exposing confidential data.
- **EX-09** — Recoverable data: The project has database backup and restore procedures, demonstrated at least once.
- **EX-10** — Accessible, responsive views: Core forms and dashboards work on common laptop/mobile screens and provide understandable validation messages.
- **EX-11** — Concurrent edits: Prevent accidental silent overwriting when two authorized users update the same request.
### 2.3 Exciting Requirements

#### A. Duplicate Issue Detection

- **E-01** — Similar-request suggestions while writing: While a client writes a request, the portal shows up to five of the most similar earlier requests from the same organization that the user is authorized to view, with their request IDs, titles, and current status. The check runs when the user pauses typing or submits, not on every keystroke. When a request is marked as Recurring (N-11), the earlier request can be selected directly from these suggestions.
- **E-02** — Bilingual similarity: Requests can be written in English or Bangla. The portal compares the meaning of requests, so that a request can match an earlier one that describes the same problem in different words or in the other language.
- **E-03** — Combined meaning and keyword matching: Meaning-based matching is combined with exact keyword matching, so that error codes, screen names, and product or module names are matched precisely. Candidate matches are narrowed by the affected product or module and a recent time period.
- **E-04** — Possible-duplicate review by DataSoft: During intake, requests that very closely match an existing request are flagged to DataSoft staff as possible duplicates. Staff can confirm the match, which links the requests, mark the new request as recurring of a closed request (N-11), or dismiss it. Requests are never merged or deleted automatically, and the matching sensitivity is set by DataSoft after testing on sample requests.
#### B. Issue Label Suggestions

- **E-05** — Suggested labels: From the request title, description, and relevant fields, the portal suggests labels from an administrator-managed list, such as Authentication, Transaction, Performance, Database, and User Interface. It can also suggest the request type and the affected product area. Suggestions work for requests written in English or Bangla.
- **E-06** — Confidence-aware suggestions: When the portal is not confident about a label, it suggests "Other" or no label instead of guessing. Users can accept, change, or remove any suggestion. Priority and severity remain user decisions.
- **E-07** — Administrator-controlled label refinement: The portal records user-confirmed labels and allows authorized administrators to refine the predefined label descriptions, keywords, and similarity rules. These changes may improve future suggestions without training or fine-tuning any machine-learning model.
- **E-08** — Emerging topic discovery: The portal periodically groups recent requests that do not fit any existing label well, together with their common keywords. An administrator can review these groups and add new labels to the list.
- **E-09** — Suggestion feedback and accuracy: The portal records whether users accept or reject duplicate and label suggestions, so that DataSoft can see how often suggestions are correct. The suggestion features are also checked against a set of sample requests in English and Bangla.
- **E-10** — Private and fail-safe suggestions: Suggestions are processed on DataSoft’s own server, and request text is not sent to outside services unless an administrator allows it. Suggestions only ever include requests the user is authorized to view. If the suggestion service is slow or unavailable, the request form keeps working without suggestions.
#### C. Sensitive Data Masking

- **E-11** — Pattern-based sensitive information detection: The portal detects common kinds of sensitive information in request descriptions and comments, and where possible in text-based attachments such as logs, using detection patterns that an administrator can configure. Examples include card numbers, account numbers, phone numbers, and one-time passwords.
- **E-12** — Masked copies: Detected values are replaced with clear labels, such as [ACCOUNT_NUMBER], so that the rest of the description or error message can still be understood. For example, “Customer account 1234567890 failed authentication” becomes “Customer account [ACCOUNT_NUMBER] failed authentication”.
- **E-13** — Review of masking: Before masked content is shared, an authorized user can review the suggested masking, correct mistaken detections, and mark information that was missed. Detection supports users but is not guaranteed to find every sensitive value.
- **E-14** — Limited retention and access: One-time passwords and full payment-card numbers are not retained in their original form. Other original content is visible only to users who have been given a specific permission to view it, not to every user with a general role, and each such view is recorded in the audit log.
- **E-15** — Masking before processing: Duplicate detection, label suggestions, and any other processing use masked text by default. If an administrator allows an external AI service, request text is masked before it is sent, never after.
#### D. Advanced Security: Tamper-Evident Service Audit Trail

- **E-16** — Protected audit records: Important actions, including client authorizations, DataSoft decisions, deliveries, verification results, closures, and reopenings, are recorded with details of who performed them and when. These records cannot be edited or deleted through the portal; corrections are added as new records.
- **E-17** — Linked audit records: Each audit record stores a cryptographic hash of the record before it, so that changing or removing an earlier record breaks the chain and can be detected during verification.
- **E-18** — Audit verification: An authorized administrator can run a check over the audit records that recomputes the chain and reports the first record where it breaks, so that any changes or missing records can be reviewed.
