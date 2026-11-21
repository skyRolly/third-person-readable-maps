public class EnvironmentProbe {
    public static void main(String[] args) {
        String[] names = {"GH_TOKEN", "GITHUB_TOKEN", "INPUT_GITHUB-TOKEN", "RELEASE_AUDITOR_TOKEN",
                          "ACTIONS_RUNTIME_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
                          "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
                          "AZURE_CLIENT_SECRET", "GOOGLE_APPLICATION_CREDENTIALS",
                          "GOOGLE_OAUTH_ACCESS_TOKEN", "DOCKER_PASSWORD", "NPM_TOKEN", "PYPI_TOKEN",
                          "TWINE_PASSWORD", "TF_TOKEN", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                          "GIT_ASKPASS", "SSH_AUTH_SOCK", "JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS",
                          "JDK_JAVA_OPTIONS", "GRADLE_OPTS"};
        int present = 0;
        for (String name : names) {
            if (System.getenv(name) != null) {
                present++;
            }
        }
        System.out.println("CREDENTIAL_NAMES_PRESENT=" + present);
    }
}
