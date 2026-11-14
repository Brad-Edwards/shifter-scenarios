import groovy.json.JsonSlurper
import hudson.model.FreeStyleProject
import hudson.model.Item
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

def instance = Jenkins.get()
def marker = new File(instance.rootDir, '.fieldlink-initialized')
if (marker.exists()) {
    return
}

def users = new JsonSlurper().parse(new File('/tmp/fieldlink-ci-users.json'))
def realm = new HudsonPrivateSecurityRealm(false)
instance.setSecurityRealm(realm)
if (User.getById('rowan.ito', false) == null) {
    realm.createAccount('rowan.ito', users.developer_password)
}
if (User.getById('ci-automation', false) == null) {
    realm.createAccount('ci-automation', users.administrator_password)
}
def strategy = new ProjectMatrixAuthorizationStrategy()
strategy.add(Jenkins.ADMINISTER, 'ci-automation')
strategy.add(Jenkins.READ, 'rowan.ito')
instance.setAuthorizationStrategy(strategy)
instance.setNumExecutors(1)
instance.setSlaveAgentPort(-1)
JenkinsLocationConfiguration.get().setUrl('https://ci.keplerops.test/')

def store = SystemCredentialsProvider.getInstance()
if (!store.credentials.any { it.id == 'fieldlink-source-read' }) {
    store.credentials.add(new UsernamePasswordCredentialsImpl(
        CredentialsScope.GLOBAL, 'fieldlink-source-read', 'FieldLink source read access',
        'rowan.ito', users.developer_password))
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
python3 -m unittest discover -s tests -v
'''))
    def archive = new ArtifactArchiver('reports/**')
    archive.setAllowEmptyArchive(true)
    project.publishersList.add(archive)
    project.updateNextBuildNumber(1842)
    project.save()
}
instance.save()
marker.text = 'initialized\n'
if (project.lastBuild == null) {
    project.scheduleBuild2(0)
}
