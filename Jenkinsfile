pipeline {
    agent any

    environment {
        // Paths and config we'll reference repeatedly
        DEV_USER = 'vamsi-ganagalla'
        K8S_DIR = 'infra/k8s'
        DOCKERHUB_USER = 'vamsi124'
        // Jenkins credential ID we configured in the UI earlier
        DOCKERHUB_CREDENTIALS = 'dockerhub-credentials'
    }

    options {
        // Keep last 10 builds; older logs/artifacts get pruned
        buildDiscarder(logRotator(numToKeepStr: '10'))
        // Don't allow concurrent builds — keeps state predictable for a single-cluster demo
        disableConcurrentBuilds()
        // Add timestamps to console output (useful for debugging slow stages)
        timestamps()
    }

    stages {
        stage('1. Checkout & Inspect') {
            steps {
                script {
                    echo "Branch: ${env.GIT_BRANCH ?: 'unknown'}"
                    echo "Commit: ${env.GIT_COMMIT ?: 'unknown'}"
                    echo "Build #: ${env.BUILD_NUMBER}"
                }
                sh 'ls -la'
                sh 'git log -1 --pretty=format:"%h %s (%an, %ar)"'
            }
        }

        stage('2. Secrets Scan (Gitleaks)') {
            steps {
                echo 'Scanning for accidentally-committed secrets...'
                // --no-banner reduces log noise
                // --redact masks any secrets in output (just-in-case defense)
                // --exit-code 1 ensures pipeline fails if ANY leak found
                // --report-path / --report-format generate artifact for archival
                sh '''
                    gitleaks detect \
                        --source . \
                        --no-banner \
                        --redact \
                        --exit-code 1 \
                        --report-path gitleaks-report.json \
                        --report-format json \
                        --verbose
                '''
            }
            post {
                always {
                    // Archive the report whether the stage passed or failed
                    archiveArtifacts artifacts: 'gitleaks-report.json', allowEmptyArchive: true
                }
            }
        }

        stage('3. Build & Unit Test') {
            parallel {
                stage('auth-service') {
                    steps {
                        dir('services/auth-service') {
                            sh './mvnw clean package -B'
                        }
                    }
                    post {
                        always {
                            // Publish JUnit results for Jenkins trend graphs
                            junit allowEmptyResults: true,
                                  testResults: 'services/auth-service/target/surefire-reports/*.xml'
                        }
                    }
                }
                stage('user-service') {
                    steps {
                        dir('services/user-service') {
                            sh './mvnw clean package -B'
                        }
                    }
                    post {
                        always {
                            junit allowEmptyResults: true,
                                  testResults: 'services/user-service/target/surefire-reports/*.xml'
                        }
                    }
                }
                stage('transaction-service') {
                    steps {
                        dir('services/transaction-service') {
                            sh './mvnw clean package -B'
                        }
                    }
                    post {
                        always {
                            junit allowEmptyResults: true,
                                  testResults: 'services/transaction-service/target/surefire-reports/*.xml'
                        }
                    }
                }
            }
        }
    }

    post {
        success {
            echo "Build #${env.BUILD_NUMBER} succeeded (stages 1-3 complete)."
        }
        failure {
            echo "Build #${env.BUILD_NUMBER} failed."
        }
        always {
            // Cleanup: clear workspace at the end to save disk
            // Comment out during debugging if you want to inspect post-mortem
            cleanWs()
        }
    }
}
