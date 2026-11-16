# Security policy

## Report a vulnerability

Report privately through [GitHub private vulnerability reporting](https://github.com/Melbournejr/FlowDrop_IOS/security/advisories/new) once the repository owner has enabled it. Do not post signing keys, passwords, access tokens or sensitive user files in public issues. If the private-reporting option is unavailable, do not publish exploit details in an issue.

## Repository and release security

- Build workflows use official Actions pinned to full commit SHAs. Checkout does not persist Git credentials. Routine build/check jobs have read-only repository permissions; CodeQL jobs can upload security results.
- CodeQL analyzes Swift and GitHub Actions on pull requests, changes to main and a weekly schedule. Dependabot checks Actions and Swift package dependencies weekly. A successful analysis is not a guarantee that the application has no vulnerabilities.
- The repository policy check rejects unpinned external Actions, write-all tokens, pull_request_target workflows, private-key material and committed credential/signing files. This check covers tracked working-tree files; it does not replace GitHub's history-aware secret scanning and push protection.
- Windows and Android installers are distributed through [GitHub Releases](https://github.com/Melbournejr/FlowDrop_IOS/releases/latest). Installed updaters verify the project's signed manifest and installer SHA-256; Android also verifies the APK identity.
- Original APK and update signing keys are kept outside the repository. Current publishing workflows upload prebuilt, signed-release assets; they do not need these keys in Actions secrets. GitHub provides the temporary GITHUB_TOKEN automatically. Do not create a long-lived personal token merely because the Secrets page is empty.

## Important limits

File-transfer traffic in current FlowDrop LAN releases still uses HTTP without encryption or cryptographic device pairing. Use a trusted network for sensitive files. Device names are not proof of identity. Protecting this repository does not encrypt transfers between devices.

Repository settings (main-branch rules, secret push protection, token defaults and release immutability) are configured separately from these files. Their enabled state must be verified in Settings; the presence of this policy does not enable them. See [.github/SECURITY-SETUP.md](.github/SECURITY-SETUP.md).
