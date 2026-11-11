# FlowDrop public signing identities

This directory contains public verification material only:

- `android-signing-certificate.pem`: the original Android APK signing certificate. Its identity is preserved when the keystore password changes.
- `update-signing-public.pem`: the existing RSA public key used by the Windows and Android update verifiers. The corresponding private key has been migrated to encrypted PKCS#8 storage without changing the public key.
- `project-signing-public.pem`: a separate Ed25519 key for signing project checksum manifests. It does not replace the application's RSA update signature.
- `key-inventory.json` and its detached `.sig`: public fingerprints signed by the project key.

Run `node security/verify-key-inventory.mjs` with Node.js to verify the inventory and all three fingerprints. Obtain the project public key or its fingerprint from a source you already trust; a signature alone cannot establish trust in a newly supplied key.

Private keys, their password files and the encrypted recovery archive are stored outside this repository. They are not GitHub release assets or Actions artifacts. No new GitHub token or repository secret was created. Current iOS builds remain unsigned and require Apple signing separately.

These keys support release integrity and project signatures. They do not encrypt LAN file transfers, provide a public-CA Windows Authenticode certificate, or enable GitHub administration settings.
