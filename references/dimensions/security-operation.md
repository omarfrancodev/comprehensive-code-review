# Security and operational dimensions

Load this reference when the changed flow crosses a trust boundary, handles concurrent/shared state, or owns a runtime resource. It refines area E without assigning extra reviewers, checks or risk scores.

## E — Security and operation

- **Authentication and authorization:** identify the principal and the exact authorization check for the action; verify that the check is bound to the requested object and operation.
- **Tenant and resource isolation:** trace identity from request to query, cache, filesystem or external resource. Try adjacent identities and cross-tenant boundaries when applicable.
- **Trust boundaries and validation:** mark untrusted inputs and the point where they are validated/normalized. Check traversal, injection, unsafe deserialization or confused-deputy behavior only when supported by the affected path.
- **Error disclosure:** inspect what the caller and logs receive on failure; distinguish necessary diagnostics from credentials, private data or exploitable internals.
- **Concurrency and idempotency:** identify shared state, lock/claim scope and retry semantics. Verify that competing operations cannot both commit incompatible ownership or repeat a non-idempotent effect.
- **Lifecycle and cleanup:** track creation, transfer, release and failure cleanup for resources owned by the changed flow. Never infer successful cleanup from intent alone.
- **Performance:** inspect a concrete workload/path and the operation that grows with it. Report a performance concern only when a credible scenario and consequence are evidenced; use measured data when claiming measured impact.

In the existing brief, name the threat/operational boundary, triggering condition, expected invariant and evidence. Keep uncertainty explicit when the deployment or workload is unknown.
