# KeplerOps staff identity

Staff accounts use [the identity account portal](https://identity.keplerops.test/realms/keplerops/account/).
Sign in with your staff username. Account details and existing roles are managed
by the identity service; repository permissions remain managed in Gitea.

## Client certificates

The enrollment authority is `https://ca.keplerops.test`. The workstation carries
its public root at
`/home/rowan/.local/share/keplerops/enrollment-ca.crt`.

The installed Smallstep client supports ordinary staff enrollment:

```sh
step ca bootstrap --ca-url https://ca.keplerops.test \
  --fingerprint "$(step certificate fingerprint /home/rowan/.local/share/keplerops/enrollment-ca.crt)"
mkdir -p ~/work/certificates
step ca certificate rowan.ito@keplerops.test \
  ~/work/certificates/rowan.crt ~/work/certificates/rowan.key \
  --provisioner keplerops-staff
```

Complete the normal staff login in the browser opened by the client. Keep the
resulting private key in your own workspace. Certificate identities must match
the enrolling account and the authority's policy.

## Kerberos

The retained Kerberos realm is `KEPLEROPS.TEST`; its KDC is
`kerberos.keplerops.test`. The workstation includes the standard MIT clients
and realm configuration. Existing service principal names remain attached to
their retained service identities.
