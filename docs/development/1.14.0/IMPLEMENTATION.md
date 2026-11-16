# FlowDrop 1.14.0 development

Base: `ebaa66049464fe20e3ba22b1031df2f62fe124c7` (merged PR #11).
One feature branch/PR; independent commits for rollback. No release/merge authorized.

## Share-code regression

Reproduction: start real Node desktop API with an empty peer list; create a ready
share on the production Java host, then advertise it over real mDNS 2.2 seconds
after starting `/api/desktop/receive`. Original desktop lookup stops at about
1.2 seconds. Original Java resolver snapshots an empty candidate collection.
Both return failure even though discovery subsequently finds the source.
This establishes a cold-discovery race in the source, not the sole possible
cause on the owner's physical devices.

Fix: bounded dynamic discovery polling, consistent Unicode whitespace/hyphen
normalization, distinct invalid/expired/unknown messages. Existing selection,
metadata bounds, local capabilities and file scope remain enforced. Failed
code probes have bounded, per-address 25/minute buckets in both hosts.

`evidence/code-before` records actual exit 1 and three failed engine cases.
`evidence/code-after` records actual exit 0 and SHA-256 exact downloads in all
three directions. Tests run on Linux Node 24 / JVM 21, not Windows/Android OS.
Additional npm unit, security integration and peer integration commands all
exit 0; details are in the command exit manifest. OS and physical verification
remain separate.

Rollback: revert the dedicated share-code commit; no data migration occurs.
