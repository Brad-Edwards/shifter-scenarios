# Orion MCP Audit

KeplerOps staging uses this utility to normalize SPDX expressions and expose a
stdio MCP tool for model-card license/schema checks. Release tags publish the
exact npm tarball and a detached signature. The consumer accepts an update only
when the assigned Cinder operator's source pull request is adopted by the
repository maintainer, the unmodified compatibility suite passes, and the
tarball signature matches the pinned server-side maintainer key. Repository
write access does not grant release-tag, signing-key, or registry-publish access.

Issue `Normalize SPDX expression output for compound licenses` tracks the 2.3.1
exception-handling regression.
