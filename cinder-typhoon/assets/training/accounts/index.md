# Rehearsal identity desk

- [Candidate notes](candidates.md)
- [Public staff directory](directory/)
- Account lookup: `POST /api/recovery/lookup`
- Account recovery: `POST /api/recovery/redeem`
- Own handover: `GET /api/handover`
- Own assignments: `GET /api/assignments`

The lookup accepts `{"account":"exact.handle"}`. Recovery accepts exactly
`{"account":"...","case_fragment":"...","staff_detail":"..."}`.
Authenticated requests use the session returned by recovery, either through the
`CINDER_REHEARSAL_SESSION` cookie or as a bearer value.
