{
    "subject": {
        "commonName": {{ toJson .Subject.CommonName }},
        "organizationalUnit": {{ if .Insecure.CR.Subject.OrganizationalUnit }}{{ toJson .Insecure.CR.Subject.OrganizationalUnit }}{{ else if .CR.Subject.OrganizationalUnit }}{{ toJson .CR.Subject.OrganizationalUnit }}{{ else }}["MaintenanceArchive"]{{ end }}
    },
    "sans": {{ toJson .SANs }},
    "keyUsage": ["digitalSignature"],
    "extKeyUsage": ["clientAuth"]
}
