pipeline {
    agent any

    environment {
        DEV_USER = 'vamsi-ganagalla'
        K8S_DIR = 'infra/k8s'
        DOCKERHUB_USER = 'vamsi124'
        DOCKERHUB_CREDENTIALS = 'dockerhub-credentials'
        // Image tag based on build number for traceability
        IMAGE_TAG = "${env.BUILD_NUMBER}"
        // Minikube IP for smoke test
        MINIKUBE_IP = '192.168.49.2'
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        disableConcurrentBuilds()
        timestamps()
    }

    stages {
        stage('1. Checkout & Inspect') {
            steps {
                script {
                    echo "Branch: ${env.GIT_BRANCH ?: 'unknown'}"
                    echo "Commit: ${env.GIT_COMMIT ?: 'unknown'}"
                    echo "Build #: ${env.BUILD_NUMBER}"
                    echo "Image tag: ${env.IMAGE_TAG}"
                }
                sh 'ls -la'
                sh 'git log -1 --pretty=format:"%h %s (%an, %ar)"'
            }
        }

        stage('2. Secrets Scan (Gitleaks)') {
            steps {
                echo 'Scanning for accidentally-committed secrets...'
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

        stage('4. Build Docker Images') {
            parallel {
                stage('auth-image') {
                    steps {
                        dir('services/auth-service') {
                            sh '''
                                docker build \
                                    -t ${DOCKERHUB_USER}/fintech-auth-service:${IMAGE_TAG} \
                                    -t ${DOCKERHUB_USER}/fintech-auth-service:latest \
                                    .
                            '''
                        }
                    }
                }
                stage('user-image') {
                    steps {
                        dir('services/user-service') {
                            sh '''
                                docker build \
                                    -t ${DOCKERHUB_USER}/fintech-user-service:${IMAGE_TAG} \
                                    -t ${DOCKERHUB_USER}/fintech-user-service:latest \
                                    .
                            '''
                        }
                    }
                }
                stage('transaction-image') {
                    steps {
                        dir('services/transaction-service') {
                            sh '''
                                docker build \
                                    -t ${DOCKERHUB_USER}/fintech-transaction-service:${IMAGE_TAG} \
                                    -t ${DOCKERHUB_USER}/fintech-transaction-service:latest \
                                    .
                            '''
                        }
                    }
                }
            }
        }

        stage('5. Image Vulnerability Scan (Trivy)') {
            steps {
                echo 'Scanning images for HIGH/CRITICAL vulnerabilities...'
                sh '''
                    # Scan each image; report HIGH+CRITICAL, FAIL only on CRITICAL
                    for service in auth-service user-service transaction-service; do
                        echo "=== Scanning fintech-${service} ==="
                        trivy image \
                            --severity HIGH,CRITICAL \
                            --no-progress \
                            --format table \
                            ${DOCKERHUB_USER}/fintech-${service}:${IMAGE_TAG} | tee trivy-${service}.txt

                        # Re-scan with --exit-code 1 only for CRITICAL to gate the build
                        trivy image \
                            --severity CRITICAL \
                            --exit-code 1 \
                            --no-progress \
                            --quiet \
                            ${DOCKERHUB_USER}/fintech-${service}:${IMAGE_TAG}
                    done
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'trivy-*.txt', allowEmptyArchive: true
                }
            }
        }

        stage('6. Push Images to Docker Hub') {
            steps {
                echo 'Pushing images to Docker Hub...'
                withCredentials([usernamePassword(
                    credentialsId: "${DOCKERHUB_CREDENTIALS}",
                    usernameVariable: 'DH_USER',
                    passwordVariable: 'DH_PASS'
                )]) {
                    sh '''
                        echo $DH_PASS | docker login -u $DH_USER --password-stdin

                        for service in auth-service user-service transaction-service; do
                            docker push ${DOCKERHUB_USER}/fintech-${service}:${IMAGE_TAG}
                            docker push ${DOCKERHUB_USER}/fintech-${service}:latest
                        done

                        docker logout
                    '''
                }
            }
        }

        stage('7. Deploy to K8s') {
            steps {
                echo 'Triggering rolling update on K8s deployments...'
                sh '''
                    sudo -u ${DEV_USER} -H kubectl rollout restart deployment \
                        auth-service user-service transaction-service

                    sudo -u ${DEV_USER} -H kubectl rollout status deployment auth-service --timeout=180s
                    sudo -u ${DEV_USER} -H kubectl rollout status deployment user-service --timeout=180s
                    sudo -u ${DEV_USER} -H kubectl rollout status deployment transaction-service --timeout=180s

                    sudo -u ${DEV_USER} -H kubectl get pods
                '''
            }
        }

        stage('8. Smoke Test') {
            steps {
                echo 'Running end-to-end smoke test...'
                sh '''
                    set -e

                    echo "=== Health checks ==="
                    for port in 30081 30082 30083; do
                        status=$(curl -s -o /dev/null -w "%{http_code}" http://${MINIKUBE_IP}:${port}/actuator/health)
                        echo "Port ${port}: ${status}"
                        [ "$status" = "200" ] || { echo "Health check failed on port ${port}"; exit 1; }
                    done

                    echo "=== Test: Register (use build-number-suffixed email for idempotency) ==="
                    REG_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
                        -X POST http://${MINIKUBE_IP}:30081/api/v1/auth/register \
                        -H "Content-Type: application/json" \
                        -d "{\\"email\\":\\"ci-build-${BUILD_NUMBER}@test.com\\",\\"password\\":\\"TestPass123!\\"}")
                    echo "Register: ${REG_STATUS}"
                    [ "$REG_STATUS" = "200" ] || { echo "Register failed"; exit 1; }

                    echo "=== Test: Login + capture token ==="
                    TOKEN=$(curl -s -X POST http://${MINIKUBE_IP}:30081/api/v1/auth/login \
                        -H "Content-Type: application/json" \
                        -d "{\\"email\\":\\"ci-build-${BUILD_NUMBER}@test.com\\",\\"password\\":\\"TestPass123!\\"}" \
                        | grep -oP '"accessToken":"[^"]+"' | cut -d'"' -f4)
                    [ -n "$TOKEN" ] || { echo "Login did not return a token"; exit 1; }
                    echo "Token acquired (first 30 chars): ${TOKEN:0:30}..."

                    echo "=== Test: Cross-pod JWT validation ==="
                    USER_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
                        -X GET http://${MINIKUBE_IP}:30082/api/v1/users/profile \
                        -H "Authorization: Bearer $TOKEN")
                    TXN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
                        -X GET http://${MINIKUBE_IP}:30083/api/v1/transactions \
                        -H "Authorization: Bearer $TOKEN")
                    echo "user-service: ${USER_STATUS}, transaction-service: ${TXN_STATUS}"
                    [ "$USER_STATUS" = "200" ] && [ "$TXN_STATUS" = "200" ] || \
                        { echo "Cross-pod JWT validation failed"; exit 1; }

                    echo "=== Test: Strict JSON rejection ==="
                    REJECT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
                        -X POST http://${MINIKUBE_IP}:30081/api/v1/auth/register \
                        -H "Content-Type: application/json" \
                        -d "{\\"email\\":\\"x@y.com\\",\\"password\\":\\"x\\",\\"isAdmin\\":true}")
                    echo "Reject malicious payload: ${REJECT_STATUS}"
                    [ "$REJECT_STATUS" = "400" ] || { echo "Strict JSON validation regression"; exit 1; }

                    echo "✓ All smoke tests passed"
                '''
            }
        }
    }

    post {
        success {
            echo "Build #${env.BUILD_NUMBER} succeeded end-to-end."
            echo "Deployed images: ${env.DOCKERHUB_USER}/fintech-{auth,user,transaction}-service:${env.IMAGE_TAG}"
        }
        failure {
            echo "Build #${env.BUILD_NUMBER} failed."
        }
        always {
            cleanWs()
        }
    }
}
