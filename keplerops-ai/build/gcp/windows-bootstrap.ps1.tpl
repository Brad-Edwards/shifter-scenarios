$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Env:ADPS_LoadDefaultDrive = 0

$HostId = "${host_id}"
$RangeInstance = "${range_instance}"
$ProjectId = "${project_id}"
$SecretSuffix = "${secret_suffix}"
$DomainDns = "${ad_domain_dns}"
$DomainNetbios = "${ad_domain_netbios}"
$ControllerIp = "${ad_controller_ip}"
$NestedBridge = "${nested_bridge_url}"
$CompanyState = [Text.Encoding]::UTF8.GetString(
    [Convert]::FromBase64String("${company_state_b64}")
) | ConvertFrom-Json
$StateRoot = "C:\ProgramData\KeplerOps"
$ReadyMarker = Join-Path $StateRoot "ready-$HostId"
New-Item -ItemType Directory -Force -Path $StateRoot | Out-Null

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class KeplerOpsNativeProfile {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct PROFILEINFO {
        public int dwSize;
        public int dwFlags;
        [MarshalAs(UnmanagedType.LPWStr)] public string lpUserName;
        [MarshalAs(UnmanagedType.LPWStr)] public string lpProfilePath;
        [MarshalAs(UnmanagedType.LPWStr)] public string lpDefaultPath;
        [MarshalAs(UnmanagedType.LPWStr)] public string lpServerName;
        [MarshalAs(UnmanagedType.LPWStr)] public string lpPolicyPath;
        public IntPtr hProfile;
    }

    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern bool LogonUser(
        string username,
        string domain,
        string password,
        int logonType,
        int logonProvider,
        out IntPtr token
    );

    [DllImport("userenv.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern bool LoadUserProfile(
        IntPtr token,
        ref PROFILEINFO profile
    );

    [DllImport("userenv.dll", SetLastError = true)]
    public static extern bool UnloadUserProfile(
        IntPtr token,
        IntPtr profile
    );

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool CloseHandle(IntPtr handle);
}
"@

$HostsPath = "$env:SystemRoot\System32\drivers\etc\hosts"
$PrivateGoogleApiEntry = "199.36.153.4 secretmanager.googleapis.com"
if (-not (Select-String `
    -Path $HostsPath `
    -Pattern "^[ \t]*199\.36\.153\.4[ \t]+.*\bsecretmanager\.googleapis\.com\b" `
    -Quiet)) {
    Add-Content -Path $HostsPath -Value $PrivateGoogleApiEntry -Encoding Ascii
}

function Get-MetadataValue([string]$Path) {
    return (Invoke-RestMethod `
        -Uri "$NestedBridge/metadata/$Path").ToString()
}

function Set-GuestAttribute([string]$Name, [string]$Value) {
    Invoke-RestMethod `
        -Method Put `
        -ContentType "application/text" `
        -Body $Value `
        -Uri "$NestedBridge/guest/$HostId/$Name" |
        Out-Null
}

Set-GuestAttribute "ready" "bootstrapping"

function Get-RangeSecret([string]$LogicalName) {
    return [Text.Encoding]::UTF8.GetString(
        (Get-RangeSecretBytes $LogicalName)
    ).Trim()
}

function Get-RangeSecretBytes([string]$LogicalName) {
    $client = [Net.WebClient]::new()
    try {
        return $client.DownloadData("$NestedBridge/secret/$LogicalName")
    }
    finally {
        $client.Dispose()
    }
}

function Get-Team([string]$Id) {
    $team = @($CompanyState.teams | Where-Object { $_.id -eq $Id })
    if ($team.Count -ne 1) {
        throw "company state team reference is invalid"
    }
    return $team[0]
}

function Get-Person([string]$Id) {
    $person = @($CompanyState.people | Where-Object { $_.id -eq $Id })
    if ($person.Count -ne 1) {
        throw "company state person reference is invalid"
    }
    return $person[0]
}

function Get-Endpoint([string]$Hostname) {
    $endpoint = @($CompanyState.endpoints | Where-Object { $_.hostname -eq $Hostname })
    if ($endpoint.Count -ne 1) {
        throw "company state endpoint reference is invalid"
    }
    return $endpoint[0]
}

function Get-IdentityUsername([string]$Id) {
    $person = @($CompanyState.people | Where-Object { $_.id -eq $Id })
    if ($person.Count -eq 1) {
        return $person[0].username
    }
    $service = @($CompanyState.service_identities | Where-Object { $_.id -eq $Id })
    if ($service.Count -eq 1) {
        return $service[0].username
    }
    throw "company state identity reference is invalid"
}

function Get-AdObjectOrNull([string]$Kind, [string]$Identity) {
    try {
        if ($Kind -eq "user") {
            return Get-ADUser -Identity $Identity
        }
        if ($Kind -eq "group") {
            return Get-ADGroup -Identity $Identity
        }
        return Get-ADComputer -Identity $Identity
    } catch {
        if (
            $_.Exception.GetType().FullName -eq
            "Microsoft.ActiveDirectory.Management.ADIdentityNotFoundException"
        ) {
            return $null
        }
        throw
    }
}

function New-DomainGroupIfMissing([string]$Name, [string]$Path) {
    if (-not (Get-AdObjectOrNull "group" $Name)) {
        New-ADGroup -Name $Name -GroupScope Global -GroupCategory Security -Path $Path
    }
}

function Add-DomainGroupMemberIfMissing([string]$Group, [string]$Member) {
    $membership = @(
        Get-ADPrincipalGroupMembership -Identity $Member |
            Where-Object { $_.SamAccountName -eq $Group }
    )
    if ($membership.Count -eq 0) {
        Add-ADGroupMember -Identity $Group -Members $Member
    }
}

function Set-DomainUser(
    [string]$Sam,
    [string]$Display,
    [string]$Mail,
    [string]$PasswordSecret,
    [string[]]$Groups,
    [string]$Path,
    [string]$Title = "",
    [string]$Department = "",
    [string]$Description = ""
) {
    $user = Get-AdObjectOrNull "user" $Sam
    $password = ConvertTo-SecureString (Get-RangeSecret $PasswordSecret) -AsPlainText -Force
    if (-not $user) {
        New-ADUser `
            -Name $Display `
            -DisplayName $Display `
            -SamAccountName $Sam `
            -UserPrincipalName "$Sam@$DomainDns" `
            -EmailAddress $Mail `
            -Path $Path `
            -AccountPassword $password `
            -Enabled $true `
            -PasswordNeverExpires $true
        $user = Get-ADUser -Identity $Sam
    }
    Set-ADAccountPassword -Identity $user -Reset -NewPassword $password
    Enable-ADAccount -Identity $user
    Set-ADUser -Identity $user -PasswordNeverExpires $true
    Set-ADUser `
        -Identity $user `
        -DisplayName $Display `
        -EmailAddress $Mail `
        -Title $Title `
        -Department $Department `
        -Company $CompanyState.organization.name `
        -Description $Description
    foreach ($group in $Groups) {
        Add-DomainGroupMemberIfMissing $group $Sam
    }
}

function Set-AuthoredComputer([object]$Endpoint, [PSCredential]$Credential = $null) {
    $team = Get-Team $Endpoint.team_ref
    $ownerUsername = Get-IdentityUsername $Endpoint.owner_ref
    $directoryServer = if ($Credential) {
        (
            [DirectoryServices.ActiveDirectory.Domain]::GetCurrentDomain().
                FindDomainController()
        ).Name
    } else {
        $DomainDns
    }
    $owner = if ($Credential) {
        Get-ADUser `
            -Identity $ownerUsername `
            -Server $directoryServer `
            -Credential $Credential
    } else {
        Get-ADUser -Identity $ownerUsername
    }
    $parameters = @{
        Identity = $env:COMPUTERNAME
        Server = $directoryServer
        DisplayName = $Endpoint.hostname
        Description = "EndpointId=$($Endpoint.id); Owner=$ownerUsername; TeamId=$($Endpoint.team_ref)"
        Location = $team.name
        ManagedBy = $owner.DistinguishedName
    }
    if ($Credential) {
        $parameters.Credential = $Credential
    }
    Set-ADComputer @parameters
}

function Set-DirectoryAcl(
    [string]$Path,
    [string]$OwnerUsername,
    [string]$TeamName,
    [bool]$TeamMayModify
) {
    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true, $false)
    $inheritance = [Security.AccessControl.InheritanceFlags]"ContainerInherit, ObjectInherit"
    $propagation = [Security.AccessControl.PropagationFlags]::None
    foreach ($rule in @(
        [Security.AccessControl.FileSystemAccessRule]::new(
            "NT AUTHORITY\SYSTEM", "FullControl", $inheritance, $propagation, "Allow"
        ),
        [Security.AccessControl.FileSystemAccessRule]::new(
            "$DomainNetbios\Domain Admins", "FullControl", $inheritance, $propagation, "Allow"
        ),
        [Security.AccessControl.FileSystemAccessRule]::new(
            "$DomainNetbios\$OwnerUsername", "Modify", $inheritance, $propagation, "Allow"
        ),
        [Security.AccessControl.FileSystemAccessRule]::new(
            "$DomainNetbios\$TeamName",
            $(if ($TeamMayModify) { "Modify" } else { "ReadAndExecute" }),
            $inheritance,
            $propagation,
            "Allow"
        )
    )) {
        $acl.AddAccessRule($rule)
    }
    $acl.SetOwner([Security.Principal.NTAccount]::new("$DomainNetbios\$OwnerUsername"))
    Set-Acl -Path $Path -AclObject $acl
}

function Set-FileAcl(
    [string]$Path,
    [string]$OwnerUsername,
    [string]$TeamName,
    [bool]$TeamMayModify
) {
    $acl = New-Object Security.AccessControl.FileSecurity
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($rule in @(
        [Security.AccessControl.FileSystemAccessRule]::new(
            "NT AUTHORITY\SYSTEM", "FullControl", "Allow"
        ),
        [Security.AccessControl.FileSystemAccessRule]::new(
            "$DomainNetbios\Domain Admins", "FullControl", "Allow"
        ),
        [Security.AccessControl.FileSystemAccessRule]::new(
            "$DomainNetbios\$OwnerUsername", "Modify", "Allow"
        ),
        [Security.AccessControl.FileSystemAccessRule]::new(
            "$DomainNetbios\$TeamName",
            $(if ($TeamMayModify) { "Modify" } else { "ReadAndExecute" }),
            "Allow"
        )
    )) {
        $acl.AddAccessRule($rule)
    }
    $acl.SetOwner([Security.Principal.NTAccount]::new("$DomainNetbios\$OwnerUsername"))
    Set-Acl -Path $Path -AclObject $acl
}

function Assert-SafeRelativePath([string]$Value) {
    $relative = $Value.Replace("/", "\")
    if (
        [IO.Path]::IsPathRooted($relative) -or
        @($relative.Split("\") | Where-Object { $_ -in @("", ".", "..") }).Count -gt 0
    ) {
        throw "company state file path is invalid"
    }
    return $relative
}

function Get-ShareRelativePath([object]$File) {
    $relative = Assert-SafeRelativePath $File.path
    if ($relative.StartsWith("Shared\")) {
        return $relative
    }
    $owner = Get-Person $File.owner_ref
    return "Users\$($owner.username)\$relative"
}

function Write-AuthoredFile(
    [object]$File,
    [string]$Path,
    [bool]$Shared
) {
    $owner = Get-Person $File.owner_ref
    $team = Get-Team $owner.team_ref
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Set-DirectoryAcl $parent $owner.username $team.name $Shared
    [IO.File]::WriteAllText(
        $Path,
        [string]$File.content,
        [Text.UTF8Encoding]::new($false)
    )
    Set-FileAcl $Path $owner.username $team.name $Shared
    $represented = [DateTimeOffset]::Parse([string]$File.updated_at).UtcDateTime
    [IO.File]::SetCreationTimeUtc($Path, $represented)
    [IO.File]::SetLastWriteTimeUtc($Path, $represented)
    [IO.File]::SetLastAccessTimeUtc($Path, $represented)
}

function Test-RepresentedTimestamp([object]$File, [string]$Path) {
    $expected = [DateTimeOffset]::Parse([string]$File.updated_at).UtcDateTime
    $actual = [IO.File]::GetLastWriteTimeUtc($Path)
    return [Math]::Abs(($actual - $expected).TotalSeconds) -lt 1
}

function Set-RepresentedWindowTimestamp([string]$Path) {
    $represented = [DateTimeOffset]::Parse(
        [string]$CompanyState.represented_window.end
    ).UtcDateTime
    [IO.File]::SetCreationTimeUtc($Path, $represented)
    [IO.File]::SetLastWriteTimeUtc($Path, $represented)
    [IO.File]::SetLastAccessTimeUtc($Path, $represented)
}

function Test-AuthoredAcl([object]$File, [string]$Path) {
    $owner = Get-Person $File.owner_ref
    $team = Get-Team $owner.team_ref
    $access = (Get-Acl $Path).Access
    $ownerValid = @($access | Where-Object {
        $_.IdentityReference.Value -eq "$DomainNetbios\$($owner.username)" -and
        ($_.FileSystemRights -band [Security.AccessControl.FileSystemRights]::Modify) -eq [Security.AccessControl.FileSystemRights]::Modify
    }).Count -gt 0
    $teamRights = if ((Assert-SafeRelativePath $File.path).StartsWith("Shared\")) {
        [Security.AccessControl.FileSystemRights]::Modify
    } else {
        [Security.AccessControl.FileSystemRights]::ReadAndExecute
    }
    $teamValid = @($access | Where-Object {
        $_.IdentityReference.Value -eq "$DomainNetbios\$($team.name)" -and
        ($_.FileSystemRights -band $teamRights) -eq $teamRights
    }).Count -gt 0
    return $ownerValid -and $teamValid
}

function Initialize-DomainContent([string]$WorkforceOu, [string]$ServiceOu) {
    foreach ($team in @($CompanyState.teams)) {
        New-DomainGroupIfMissing $team.name $WorkforceOu
        Set-ADGroup `
            -Identity $team.name `
            -Description "TeamId=$($team.id); LeadRef=$($team.lead_ref)"
    }
    foreach ($group in @(
        "QA",
        "ML Engineering",
        "Release Managers",
        "Security Administrators",
        "Directory Readers"
    )) {
        New-DomainGroupIfMissing $group $WorkforceOu
    }

    $challengeGroups = @{
        "qa.intern" = @("QA", "Domain Users")
        "ml.engineer" = @("ML Engineering", "Domain Users")
        "release.manager" = @("Release Managers", "Domain Users")
    }
    $passwordSecrets = @{
        "qa.intern" = "ad-qa-password"
        "ml.engineer" = "ad-ml-engineer-password"
        "release.manager" = "ad-release-manager-password"
    }
    foreach ($person in @($CompanyState.people)) {
        $team = Get-Team $person.team_ref
        Set-DomainUser `
            $person.username `
            $person.display_name `
            $person.email `
            $passwordSecrets[$person.username] `
            @($team.name) `
            $WorkforceOu `
            $person.title `
            $team.name `
            "PersonId=$($person.id); TeamId=$($person.team_ref)"
        foreach ($group in $challengeGroups[$person.username]) {
            Add-DomainGroupMemberIfMissing $group $person.username
        }
    }

    Set-DomainUser `
        "guardrail.admin" `
        "Guardrail Administrator" `
        "guardrail.admin@$DomainDns" `
        "ad-guardrail-admin-password" `
        @("Security Administrators", "Domain Users") `
        $WorkforceOu `
        "Guardrail Administrator" `
        "Security" `
        "Scenario identity retained for the guardrail administration challenge"
    Set-DomainUser `
        "svc.keycloak" `
        "Keycloak Directory Bind" `
        "svc.keycloak@$DomainDns" `
        "ad-federation-bind-password" `
        @("Directory Readers") `
        $ServiceOu `
        "Directory Bind Service" `
        "Platform Operations" `
        "Least-privilege Keycloak federation bind identity"

    foreach ($team in @($CompanyState.teams)) {
        $lead = Get-Person $team.lead_ref
        Set-ADGroup -Identity $team.name -ManagedBy (Get-ADUser $lead.username).DistinguishedName
    }
}

function Initialize-CompanyShare([string]$ShareRoot, [string]$CaCertificatePath) {
    New-Item -ItemType Directory -Force -Path $ShareRoot | Out-Null
    if (-not (Get-SmbShare -Name "Company" -ErrorAction SilentlyContinue)) {
        New-SmbShare `
            -Name "Company" `
            -Path $ShareRoot `
            -FullAccess "$DomainNetbios\Domain Admins" `
            -ChangeAccess "$DomainNetbios\Domain Users" | Out-Null
    }
    $rootAcl = New-Object Security.AccessControl.DirectorySecurity
    $rootAcl.SetAccessRuleProtection($true, $false)
    $inheritance = [Security.AccessControl.InheritanceFlags]"ContainerInherit, ObjectInherit"
    $propagation = [Security.AccessControl.PropagationFlags]::None
    foreach ($rule in @(
        [Security.AccessControl.FileSystemAccessRule]::new(
            "NT AUTHORITY\SYSTEM", "FullControl", $inheritance, $propagation, "Allow"
        ),
        [Security.AccessControl.FileSystemAccessRule]::new(
            "$DomainNetbios\Domain Admins", "FullControl", $inheritance, $propagation, "Allow"
        ),
        [Security.AccessControl.FileSystemAccessRule]::new(
            "$DomainNetbios\Domain Users", "ReadAndExecute", $inheritance, $propagation, "Allow"
        )
    )) {
        $rootAcl.AddAccessRule($rule)
    }
    Set-Acl -Path $ShareRoot -AclObject $rootAcl

    $supportRoot = Join-Path $ShareRoot ".keplerops"
    New-Item -ItemType Directory -Force -Path $supportRoot | Out-Null
    Copy-Item -Force $CaCertificatePath (Join-Path $supportRoot "ca.crt")
    foreach ($file in @($CompanyState.files)) {
        $relative = Get-ShareRelativePath $file
        Write-AuthoredFile $file (Join-Path $ShareRoot $relative) $relative.StartsWith("Shared\")
    }
}

function Invoke-ProfileInitialization([string]$Username, [string]$CaCertificatePath) {
    $passwordSecret = switch ($Username) {
        "qa.intern" { "ad-qa-password" }
        "ml.engineer" { "ad-ml-engineer-password" }
        "release.manager" { "ad-release-manager-password" }
        default { throw "profile initialization identity is invalid" }
    }
    $password = Get-RangeSecret $passwordSecret
    $token = [IntPtr]::Zero
    $profileLoaded = $false
    $profile = [KeplerOpsNativeProfile+PROFILEINFO]::new()
    $profile.dwSize = [Runtime.InteropServices.Marshal]::SizeOf($profile)
    $profile.lpUserName = $Username
    try {
        if (-not [KeplerOpsNativeProfile]::LogonUser(
            $Username,
            $DomainNetbios,
            $password,
            2,
            0,
            [ref]$token
        )) {
            throw [ComponentModel.Win32Exception]::new(
                [Runtime.InteropServices.Marshal]::GetLastWin32Error()
            )
        }
        if (-not [KeplerOpsNativeProfile]::LoadUserProfile(
            $token,
            [ref]$profile
        )) {
            throw [ComponentModel.Win32Exception]::new(
                [Runtime.InteropServices.Marshal]::GetLastWin32Error()
            )
        }
        $profileLoaded = $true

        $identity = [Security.Principal.WindowsIdentity]::new($token)
        $impersonation = $identity.Impersonate()
        try {
            $certificate = [Security.Cryptography.X509Certificates.X509Certificate2]::new(
                $CaCertificatePath
            )
            $store = [Security.Cryptography.X509Certificates.X509Store]::new(
                [Security.Cryptography.X509Certificates.StoreName]::Root,
                [Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser
            )
            try {
                $store.Open(
                    [Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite
                )
                if (-not @($store.Certificates | Where-Object {
                    $_.Thumbprint -eq $certificate.Thumbprint
                })) {
                    $store.Add($certificate)
                }
            }
            finally {
                $store.Dispose()
                $certificate.Dispose()
            }
        }
        finally {
            $impersonation.Undo()
            $impersonation.Dispose()
            $identity.Dispose()
        }
    }
    finally {
        if ($profileLoaded) {
            [KeplerOpsNativeProfile]::UnloadUserProfile(
                $token,
                $profile.hProfile
            ) | Out-Null
        }
        if ($token -ne [IntPtr]::Zero) {
            [KeplerOpsNativeProfile]::CloseHandle($token) | Out-Null
        }
    }
}

function Get-ProfilePath([string]$Username) {
    $sid = ([Security.Principal.NTAccount]::new(
        "$DomainNetbios\$Username"
    )).Translate([Security.Principal.SecurityIdentifier]).Value
    $profile = Get-CimInstance Win32_UserProfile | Where-Object { $_.SID -eq $sid }
    if (-not $profile -or -not (Test-Path $profile.LocalPath)) {
        throw "domain user profile is missing"
    }
    return $profile.LocalPath
}

function Get-ToolHistory([string]$Username) {
    switch ($Username) {
        "qa.intern" {
            return @(
                "Get-ChildItem \\ad-dc-01\Company\Users\qa.intern\Documents\Evaluation",
                "git -C evaluation-tooling log --oneline -5",
                "python .\tools\check_slice_metadata.py dataset-eval-v22"
            )
        }
        "ml.engineer" {
            return @(
                "git -C model-release status --short",
                "jupyter notebook .\Projects\orion\candidate-18-evaluation.ipynb",
                "python .\tools\summarize_evaluation.py --experiment experiment-orion-18"
            )
        }
        "release.manager" {
            return @(
                "Get-Content \\ad-dc-01\Company\Shared\Release\orion-18-checklist.md",
                "git -C model-release show f8b62ea61f40 --stat",
                "certutil.exe -user -store Root"
            )
        }
        default {
            throw "company state profile role is invalid"
        }
    }
}

function Initialize-EndpointProfiles(
    [object]$Endpoint,
    [string]$CaCertificatePath,
    [string]$CompanyDrive
) {
    $files = @($CompanyState.files | Where-Object { $_.endpoint_ref -eq $Endpoint.id })
    $owners = @($files | ForEach-Object { $_.owner_ref } | Sort-Object -Unique)
    foreach ($ownerRef in $owners) {
        $person = Get-Person $ownerRef
        $team = Get-Team $person.team_ref
        Invoke-ProfileInitialization $person.username $CaCertificatePath
        $profilePath = Get-ProfilePath $person.username

        foreach ($file in @($files | Where-Object { $_.owner_ref -eq $ownerRef })) {
            $relative = Assert-SafeRelativePath $file.path
            $destination = Join-Path $profilePath $relative
            Write-AuthoredFile $file $destination $relative.StartsWith("Shared\")
            $sharePath = Join-Path "$CompanyDrive`:\" (Get-ShareRelativePath $file)
            if (-not (Test-Path $sharePath)) {
                throw "authored SMB file is unavailable from the endpoint"
            }
        }

        $historyPath = Join-Path $profilePath `
            "AppData\Roaming\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt"
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $historyPath) | Out-Null
        [IO.File]::WriteAllLines(
            $historyPath,
            (Get-ToolHistory $person.username),
            [Text.UTF8Encoding]::new($false)
        )
        Set-FileAcl $historyPath $person.username $team.name $false
        Set-RepresentedWindowTimestamp $historyPath

        $gitConfig = @"
[user]
    name = $($person.display_name)
    email = $($person.email)
[init]
    defaultBranch = main
"@
        $gitConfigPath = Join-Path $profilePath ".gitconfig"
        [IO.File]::WriteAllText(
            $gitConfigPath,
            $gitConfig,
            [Text.UTF8Encoding]::new($false)
        )
        Set-FileAcl $gitConfigPath $person.username $team.name $false
        Set-RepresentedWindowTimestamp $gitConfigPath

        $certificate = Get-PfxCertificate -FilePath $CaCertificatePath
        $certificateContext = @{
            directory_domain = $DomainDns
            endpoint = $Endpoint.hostname
            root_ca_subject = $certificate.Subject
            root_ca_thumbprint = $certificate.Thumbprint
            username = $person.username
        } | ConvertTo-Json
        $contextPath = Join-Path $profilePath "AppData\Local\KeplerOps\certificate-context.json"
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $contextPath) | Out-Null
        [IO.File]::WriteAllText(
            $contextPath,
            $certificateContext,
            [Text.UTF8Encoding]::new($false)
        )
        Set-FileAcl $contextPath $person.username $team.name $false
        Set-RepresentedWindowTimestamp $contextPath

        $recentRoot = Join-Path $profilePath "AppData\Roaming\Microsoft\Windows\Recent"
        New-Item -ItemType Directory -Force -Path $recentRoot | Out-Null
        $recentFile = @($files | Where-Object { $_.owner_ref -eq $ownerRef })[0]
        if ($recentFile) {
            $target = Join-Path $profilePath (Assert-SafeRelativePath $recentFile.path)
            $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut(
                (Join-Path $recentRoot "$($recentFile.id).lnk")
            )
            $shortcut.TargetPath = $target
            $shortcut.Save()
            Set-FileAcl `
                (Join-Path $recentRoot "$($recentFile.id).lnk") `
                $person.username `
                $team.name `
                $false
            Set-RepresentedWindowTimestamp `
                (Join-Path $recentRoot "$($recentFile.id).lnk")
        }
    }
}

function Assert-DomainContent([string]$ShareRoot) {
    $domain = Get-ADDomain
    if ($domain.DNSRoot -ne $CompanyState.organization.directory_domain) {
        throw "directory domain readback failed"
    }
    foreach ($person in @($CompanyState.people)) {
        $team = Get-Team $person.team_ref
        $user = Get-ADUser $person.username -Properties DisplayName, Title, Department
        if (
            $user.DisplayName -ne $person.display_name -or
            $user.Title -ne $person.title -or
            $user.Department -ne $team.name
        ) {
            throw "authored user readback failed"
        }
        if (-not (Get-ADGroupMember $team.name | Where-Object {
            $_.SamAccountName -eq $person.username
        })) {
            throw "authored team membership readback failed"
        }
    }
    if ((Get-SmbShare -Name Company).Path -ne $ShareRoot) {
        throw "company share readback failed"
    }
    foreach ($file in @($CompanyState.files)) {
        $path = Join-Path $ShareRoot (Get-ShareRelativePath $file)
        if (
            -not (Test-Path $path -PathType Leaf) -or
            -not (Test-RepresentedTimestamp $file $path) -or
            -not (Test-AuthoredAcl $file $path)
        ) {
            throw "authored SMB file readback failed"
        }
    }
}

function Assert-EndpointContent(
    [object]$Endpoint,
    [string]$CaCertificatePath,
    [string]$CompanyDrive,
    [PSCredential]$DomainCredential
) {
    $computer = Get-CimInstance Win32_ComputerSystem
    if (-not $computer.PartOfDomain -or $computer.Domain -ne $DomainDns) {
        throw "endpoint domain membership readback failed"
    }
    $directoryServer = (
        [DirectoryServices.ActiveDirectory.Domain]::GetCurrentDomain().
            FindDomainController()
    ).Name
    $adComputer = Get-ADComputer `
        -Identity $env:COMPUTERNAME `
        -Server $directoryServer `
        -Credential $DomainCredential `
        -Properties DisplayName, Description, Location, ManagedBy
    $team = Get-Team $Endpoint.team_ref
    $ownerUsername = Get-IdentityUsername $Endpoint.owner_ref
    $owner = Get-ADUser `
        -Identity $ownerUsername `
        -Server $directoryServer `
        -Credential $DomainCredential
    if (
        $adComputer.DisplayName -ne $Endpoint.hostname -or
        $adComputer.Location -ne $team.name -or
        $adComputer.ManagedBy -ne $owner.DistinguishedName
    ) {
        throw "authored computer readback failed"
    }
    $certificate = Get-PfxCertificate -FilePath $CaCertificatePath
    if (-not (Get-ChildItem Cert:\LocalMachine\Root | Where-Object {
        $_.Thumbprint -eq $certificate.Thumbprint
    })) {
        throw "endpoint certificate trust readback failed"
    }
    foreach ($file in @($CompanyState.files | Where-Object {
        $_.endpoint_ref -eq $Endpoint.id
    })) {
        $person = Get-Person $file.owner_ref
        $profilePath = Get-ProfilePath $person.username
        $path = Join-Path $profilePath (Assert-SafeRelativePath $file.path)
        $sharePath = Join-Path "$CompanyDrive`:\" (Get-ShareRelativePath $file)
        $historyPath = Join-Path $profilePath `
            "AppData\Roaming\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt"
        $contextPath = Join-Path $profilePath `
            "AppData\Local\KeplerOps\certificate-context.json"
        if (
            -not (Test-Path $path -PathType Leaf) -or
            -not (Test-RepresentedTimestamp $file $path) -or
            -not (Test-Path $sharePath -PathType Leaf) -or
            -not (Test-Path $historyPath -PathType Leaf) -or
            -not (Test-Path $contextPath -PathType Leaf)
        ) {
            throw "authored endpoint profile readback failed"
        }
    }
}

function Complete-Bootstrap([string]$Role) {
    $readback = @{
        domain = $DomainDns
        host_id = $HostId
        instance_id = Get-MetadataValue "instance/id"
        role = $Role
        status = "ready"
    } | ConvertTo-Json -Compress
    New-Item -ItemType File -Force -Path $ReadyMarker | Out-Null
    Set-GuestAttribute "readback" $readback
    Set-GuestAttribute "ready" "ready"
}

Set-TimeZone -Id "UTC"
Set-Service W32Time -StartupType Automatic
Start-Service W32Time
Enable-NetFirewallRule -DisplayGroup "Remote Desktop" -ErrorAction SilentlyContinue

if ($CompanyState.organization.directory_domain -ne $DomainDns) {
    throw "company state authority does not match the deployed domain"
}

if ($HostId -eq "ad-dc-01") {
    $domainAdminPassword = Get-RangeSecret "ad-domain-admin-password"
    & net.exe user Administrator $domainAdminPassword | Out-Null
    Install-WindowsFeature AD-Domain-Services, DNS, GPMC, FS-FileServer -IncludeManagementTools |
        Out-Null
    $adapter = Get-NetAdapter | Where-Object Status -eq "Up" | Select-Object -First 1
    Set-DnsClientServerAddress -InterfaceIndex $adapter.ifIndex -ServerAddresses $ControllerIp

    $ldapsRoot = Join-Path $StateRoot "ldaps"
    $ldapsArchive = Join-Path $StateRoot "tls-ad-dc-01.tar"
    New-Item -ItemType Directory -Force -Path $ldapsRoot | Out-Null
    [IO.File]::WriteAllBytes($ldapsArchive, (Get-RangeSecretBytes "tls-ad-dc-01"))
    & tar.exe -xf $ldapsArchive -C $ldapsRoot
    $pfxPassword = ConvertTo-SecureString $domainAdminPassword -AsPlainText -Force
    if (-not (Get-ChildItem Cert:\LocalMachine\My | Where-Object {
        $_.Subject -eq "CN=ad-dc-01.keplerops.lab" -and $_.HasPrivateKey
    })) {
        Import-PfxCertificate `
            -FilePath (Join-Path $ldapsRoot "tls.pfx") `
            -CertStoreLocation Cert:\LocalMachine\My `
            -Password $pfxPassword | Out-Null
    }
    Import-Certificate `
        -FilePath (Join-Path $ldapsRoot "ca.crt") `
        -CertStoreLocation Cert:\LocalMachine\Root | Out-Null

    $computerSystem = Get-CimInstance Win32_ComputerSystem
    if ($computerSystem.DomainRole -lt 4) {
        $safeMode = ConvertTo-SecureString $domainAdminPassword -AsPlainText -Force
        Install-ADDSForest `
            -DomainName $DomainDns `
            -DomainNetbiosName $DomainNetbios `
            -InstallDns `
            -SafeModeAdministratorPassword $safeMode `
            -NoRebootOnCompletion `
            -Force
        & shutdown.exe /r /t 5 /f | Out-Null
        exit 0
    }

    Import-Module ActiveDirectory
    $domain = $null
    foreach ($attempt in 1..120) {
        try {
            $domain = Get-ADDomain -ErrorAction Stop
            break
        }
        catch {
            Start-Sleep -Seconds 5
        }
    }
    if (-not $domain) {
        throw "Active Directory Web Services did not become ready"
    }
    $domainDn = $domain.DistinguishedName
    $ouDefinitions = @(
        @{ Name = "Workforce"; Path = $domainDn },
        @{ Name = "Service Accounts"; Path = $domainDn },
        @{ Name = "Endpoints"; Path = $domainDn }
    )
    foreach ($definition in $ouDefinitions) {
        $ou = Get-ADOrganizationalUnit `
            -LDAPFilter "(ou=$($definition.Name))" `
            -SearchBase $definition.Path `
            -SearchScope OneLevel `
            -ErrorAction SilentlyContinue
        if (-not $ou) {
            New-ADOrganizationalUnit -Name $definition.Name -Path $definition.Path
        }
    }
    $workforceOu = "OU=Workforce,$domainDn"
    $serviceOu = "OU=Service Accounts,$domainDn"
    $defaultPasswordPolicy = Get-ADDefaultDomainPasswordPolicy
    try {
        if ($defaultPasswordPolicy.ComplexityEnabled) {
            Set-ADDefaultDomainPasswordPolicy `
                -Identity $DomainDns `
                -ComplexityEnabled $false
        }
        Initialize-DomainContent $workforceOu $serviceOu
    }
    finally {
        Set-ADDefaultDomainPasswordPolicy `
            -Identity $DomainDns `
            -ComplexityEnabled $defaultPasswordPolicy.ComplexityEnabled
    }
    Set-AuthoredComputer (Get-Endpoint $HostId)
    try {
        $dcRecords = @(
            Get-DnsServerResourceRecord `
                -ZoneName $DomainDns `
                -Name "ad-dc-01" `
                -ErrorAction Stop
        )
    }
    catch {
        $dcRecords = @()
    }
    $dcAddress = @($dcRecords | Where-Object {
        $_.RecordType -eq "A" -and
        $_.RecordData.IPv4Address.IPAddressToString -eq $ControllerIp
    })
    if ($dcAddress.Count -eq 0) {
        foreach ($record in $dcRecords) {
            Remove-DnsServerResourceRecord `
                -ZoneName $DomainDns `
                -InputObject $record `
                -Force
        }
        Add-DnsServerResourceRecordA `
            -ZoneName $DomainDns `
            -Name "ad-dc-01" `
            -IPv4Address $ControllerIp
    }

    $shareRoot = "C:\KeplerOps\Company"
    Initialize-CompanyShare $shareRoot (Join-Path $ldapsRoot "ca.crt")
    Assert-DomainContent $shareRoot
    Complete-Bootstrap "domain-controller"
    exit 0
}

$adapter = Get-NetAdapter | Where-Object Status -eq "Up" | Select-Object -First 1
Set-DnsClientServerAddress -InterfaceIndex $adapter.ifIndex -ServerAddresses $ControllerIp
while (-not (Test-NetConnection -ComputerName $ControllerIp -Port 389 -InformationLevel Quiet)) {
    Start-Sleep -Seconds 10
}
$domainControllerReady = $false
foreach ($attempt in 1..120) {
    & nltest.exe "/dsgetdc:$DomainDns" "/force" | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $domainControllerReady = $true
        break
    }
    Start-Sleep -Seconds 10
}
if (-not $domainControllerReady) {
    throw "Active Directory domain locator did not become ready"
}

$domainAdminPassword = ConvertTo-SecureString `
    (Get-RangeSecret "ad-domain-admin-password") `
    -AsPlainText `
    -Force
$domainCredential = [PSCredential]::new(
    "$DomainNetbios\Administrator",
    $domainAdminPassword
)
$computer = Get-CimInstance Win32_ComputerSystem
if (-not $computer.PartOfDomain) {
    Add-Computer `
        -DomainName $DomainDns `
        -Credential $domainCredential `
        -Force
    & shutdown.exe /r /t 5 /f | Out-Null
    exit 0
}

Install-WindowsFeature RSAT-AD-PowerShell | Out-Null
Import-Module ActiveDirectory
$endpoint = Get-Endpoint $HostId
Set-AuthoredComputer $endpoint $domainCredential

$domainControllerHost = "ad-dc-01.$DomainDns"
$shareRoot = "\\$domainControllerHost\Company"
while (-not (Test-NetConnection -ComputerName $domainControllerHost -Port 445 -InformationLevel Quiet)) {
    Start-Sleep -Seconds 10
}
if (Get-PSDrive -Name KCompany -ErrorAction SilentlyContinue) {
    Remove-PSDrive -Name KCompany -Force
}
New-PSDrive `
    -Name KCompany `
    -PSProvider FileSystem `
    -Root $shareRoot `
    -Credential $domainCredential | Out-Null

$caCertificatePath = Join-Path $StateRoot "keplerops-root-ca.crt"
Copy-Item -Force "KCompany:\.keplerops\ca.crt" $caCertificatePath
Import-Certificate `
    -FilePath $caCertificatePath `
    -CertStoreLocation Cert:\LocalMachine\Root | Out-Null
Initialize-EndpointProfiles $endpoint $caCertificatePath "KCompany"

$profileRoot = if ($HostId -eq "ml-workstation-01") {
    "C:\KeplerOps\ML-Engineering"
} else {
    "C:\KeplerOps\Workforce"
}
New-Item -ItemType Directory -Force -Path $profileRoot | Out-Null
$endpointProfile = @{
    directory_domain = $DomainDns
    endpoint_id = $endpoint.id
    hostname = $endpoint.hostname
    owner_ref = $endpoint.owner_ref
    range_instance = $RangeInstance
    team_ref = $endpoint.team_ref
} | ConvertTo-Json
[IO.File]::WriteAllText(
    (Join-Path $profileRoot "endpoint-profile.json"),
    $endpointProfile,
    [Text.UTF8Encoding]::new($false)
)

Assert-EndpointContent $endpoint $caCertificatePath "KCompany" $domainCredential
Remove-PSDrive -Name KCompany -Force
Complete-Bootstrap "domain-member"
