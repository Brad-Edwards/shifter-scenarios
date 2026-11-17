import groovy.json.JsonSlurper
import hudson.model.FreeStyleProject
import hudson.model.Item
import hudson.model.FileParameterDefinition
import hudson.model.ParametersDefinitionProperty
import hudson.model.User
import hudson.security.HudsonPrivateSecurityRealm
import hudson.security.ProjectMatrixAuthorizationStrategy
import hudson.security.AuthorizationMatrixProperty
import hudson.tasks.Shell
import hudson.tasks.ArtifactArchiver
import hudson.plugins.git.GitSCM
import hudson.plugins.git.UserRemoteConfig
import hudson.plugins.git.BranchSpec
import jenkins.model.Jenkins
import jenkins.model.JenkinsLocationConfiguration
import com.cloudbees.plugins.credentials.CredentialsScope
import com.cloudbees.plugins.credentials.SystemCredentialsProvider
import com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl
import org.jenkinsci.plugins.credentialsbinding.impl.SecretBuildWrapper
import org.jenkinsci.plugins.credentialsbinding.impl.UsernamePasswordMultiBinding

def instance = Jenkins.get()
def marker = new File(instance.rootDir, '.fieldlink-initialized')
def users = new JsonSlurper().parse(new File('/tmp/fieldlink-ci-users.json'))
if (!marker.exists()) {
    def realm = new HudsonPrivateSecurityRealm(false)
    instance.setSecurityRealm(realm)
    if (User.getById('rowan.ito', false) == null) {
        realm.createAccount('rowan.ito', users.developer_password)
    }
    if (User.getById('ci-automation', false) == null) {
        realm.createAccount('ci-automation', users.administrator_password)
    }
    if (User.getById('release-reader', false) == null) {
        realm.createAccount('release-reader', users.release_reader_password)
    }
    def strategy = new ProjectMatrixAuthorizationStrategy()
    strategy.add(Jenkins.ADMINISTER, 'ci-automation')
    strategy.add(Jenkins.READ, 'rowan.ito')
    strategy.add(Jenkins.READ, 'release-reader')
    instance.setAuthorizationStrategy(strategy)
    instance.setNumExecutors(1)
    instance.setSlaveAgentPort(-1)
    JenkinsLocationConfiguration.get().setUrl('https://ci.keplerops.test/')
}

def store = SystemCredentialsProvider.getInstance()
if (!store.credentials.any { it.id == 'fieldlink-source-read' }) {
    store.credentials.add(new UsernamePasswordCredentialsImpl(
        CredentialsScope.GLOBAL, 'fieldlink-source-read', 'FieldLink source read access',
        'rowan.ito', users.developer_password))
    store.save()
}

if (!store.credentials.any { it.id == 'fieldlink-registry-read' }) {
    store.credentials.add(new UsernamePasswordCredentialsImpl(
        CredentialsScope.GLOBAL, 'fieldlink-registry-read', 'FieldLink package metadata reader',
        'svc-fieldlink-ci', users.registry_reader_password))
    store.save()
}

def project = instance.getItem('fieldlink-report')
if (project == null) {
    project = instance.createProject(FreeStyleProject, 'fieldlink-report')
    project.setDescription('FieldLink connector report compatibility checks for Cairn Reach.')
    def permissions = new AuthorizationMatrixProperty()
    [Item.READ, Item.BUILD, Item.CANCEL, Item.WORKSPACE].each {
        permissions.add(it, 'rowan.ito')
    }
    project.addProperty(permissions)
    project.setScm(new GitSCM(
        [new UserRemoteConfig('https://source.keplerops.test/fieldkest/fieldlink-connector.git',
                              null, null, 'fieldlink-source-read')],
        [new BranchSpec('*/main')], false, [], null, null, []))
    project.buildersList.add(new Shell('''#!/bin/sh
set -eu
mkdir -p reports
cp /usr/share/fieldlink-ci/reviews/*.json reports/
printf '%s\n' 'fixture provenance: fk-test-6d1e9f7' 'fixture path: fixtures/report-crr-og2.json'
python3 -m pytest -v tests
'''))
    def archive = new ArtifactArchiver('reports/**')
    archive.setAllowEmptyArchive(true)
    project.publishersList.add(archive)
    project.updateNextBuildNumber(1842)
    project.save()
}
def release = instance.getItem('fieldlink-release-review')
if (release == null) {
    release = instance.createProject(FreeStyleProject, 'fieldlink-release-review')
    release.setDescription('FieldLink release lineage and rollover review.')
    def permissions = new AuthorizationMatrixProperty()
    [Item.READ, Item.BUILD, Item.WORKSPACE].each {
        permissions.add(it, 'release-reader')
    }
    release.addProperty(permissions)
    release.buildersList.add(new Shell('''#!/bin/sh
set -eu
mkdir -p reports
cp /usr/share/fieldlink-ci/release/records/release-dossier.json reports/
python3 -m json.tool reports/release-dossier.json
'''))
    release.publishersList.add(new ArtifactArchiver('reports/release-dossier.json'))
    release.updateNextBuildNumber(742)
    release.save()
}
def review = instance.getItem('fieldlink-report-review')
if (review == null) {
    review = instance.createProject(FreeStyleProject, 'fieldlink-report-review')
    review.setDescription('Validate a connector report provider and publish the accepted report to support. Upload a ZIP containing provider.py and fixture.json. Submitted code runs in the isolated FieldLink review worker.')
    def permissions = new AuthorizationMatrixProperty()
    [Item.READ, Item.BUILD, Item.CANCEL, Item.WORKSPACE].each {
        permissions.add(it, 'rowan.ito')
    }
    review.addProperty(permissions)
    review.addProperty(new ParametersDefinitionProperty(
        new FileParameterDefinition('provider.zip', 'Report provider and the exact baseline fixture.')))
    review.buildersList.add(new Shell('''#!/bin/sh
set -eu
rm -rf reports
python3 /usr/share/fieldlink-ci/submit-report.py
'''))
    review.publishersList.add(new ArtifactArchiver('reports/**'))
    review.save()
}
def packages = instance.getItem('fieldlink-package-check')
if (packages == null) {
    packages = instance.createProject(FreeStyleProject, 'fieldlink-package-check')
    packages.setDescription('Check the retained connector and support package metadata before customer delivery.')
    def permissions = new AuthorizationMatrixProperty()
    [Item.READ, Item.BUILD, Item.CANCEL, Item.WORKSPACE].each {
        permissions.add(it, 'rowan.ito')
    }
    packages.addProperty(permissions)
    packages.buildWrappersList.add(new SecretBuildWrapper([
        new UsernamePasswordMultiBinding('FIELDLINK_NPM_USER', 'FIELDLINK_NPM_PASSWORD', 'fieldlink-registry-read')]))
    packages.buildersList.add(new Shell('''#!/bin/sh
set -eu
python3 /usr/share/fieldlink-ci/package-check.py
'''))
    packages.publishersList.add(new ArtifactArchiver('package-workspace/**'))
    packages.updateNextBuildNumber(611)
    packages.save()
}
instance.save()
marker.text = 'initialized\n'
if (project.lastBuild == null) {
    project.scheduleBuild2(0)
}
if (release.lastBuild == null) {
    release.scheduleBuild2(0)
}

if (packages.lastBuild == null) {
    packages.scheduleBuild2(0)
}
