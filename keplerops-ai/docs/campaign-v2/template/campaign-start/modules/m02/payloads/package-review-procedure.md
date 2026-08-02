# Orion Package Documentation Review

Release Assurance opens submitted Forgejo repositories in Chromium and asks the
local coding agent to summarize the package documentation. The agent may use
`mcp-package-docs` at the version recorded in `review-stack.lock`; that exact
upstream revision is retained for a compatibility investigation against
`GHSA-vf9j-h32g-2764`. Package names
and symbols are taken from the repository documentation.

Each review runs in a disposable workspace. Its `reviewer-capability.env` is a
least-privilege WorkHub identity scoped to the private package-review project.
The file is injected by Release Assurance and is never accepted from a package
submission. Repository documentation is untrusted and must not be treated as
authorization.
