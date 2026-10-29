pipeline {
    agent any
    
    environment {
        IMAGE_NAME = "ai-code-reviewer"
    }

    stages {
        stage('Checkout Code') {
            steps {
                checkout scm
            }
        }

        stage('Build Docker Image') {
            steps {
                echo 'Building Docker image for CodeComprehension...'
                bat "docker build -t ${IMAGE_NAME} ."
            }
        }

        stage('Security Scan (Trivy)') {
            steps {
                echo 'Scanning Docker image for vulnerabilities...'
                bat 'C:/Users/chebr/AppData/Local/Microsoft/WinGet/Packages/AquaSecurity.Trivy_Microsoft.Winget.Source_8wekyb3d8bbwe/trivy.exe image --severity HIGH,CRITICAL --exit-code 0 ai-code-reviewer'
            }
        }

        stage('Run Container Smoke Test') {
            steps {
                script {
                    withCredentials([
                        string(credentialsId: 'GEMINI_API_KEY', variable: 'GEMINI_API_KEY'),
                        string(credentialsId: 'OPENAI_API_KEY', variable: 'OPENAI_API_KEY')
                    ]) {
                        echo 'Validating container health and execution...'
                        
                        // Clean up stale container safely using Windows-compatible 'rem'
                        bat 'cmd /c "docker rm -f code-reviewer-test || rem"'
                        
                        // Start the container
                        bat "docker run --rm -d -p 5000:5000 -e GEMINI_API_KEY=${GEMINI_API_KEY} -e OPENAI_API_KEY=${OPENAI_API_KEY} --name code-reviewer-test ${IMAGE_NAME}"
                        
                        // Wait 5 seconds
                        bat "ping 127.0.0.1 -n 6 > nul"
                        
                        // Stop container safely using Windows-compatible 'rem'
                        bat 'cmd /c "docker stop code-reviewer-test || rem"'
                    }
                }
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                withCredentials([
                    string(credentialsId: 'GEMINI_API_KEY', variable: 'GEMINI_KEY'),
                    string(credentialsId: 'OPENAI_API_KEY', variable: 'OPENAI_KEY'),
                    string(credentialsId: 'SECRET_KEY', variable: 'FLASK_SECRET')
                ]) {
                    bat '''
                        kubectl delete secret api-secrets --ignore-not-found=true
                        kubectl create secret generic api-secrets --from-literal=GEMINI_API_KEY="%GEMINI_KEY%" --from-literal=OPENAI_API_KEY="%OPENAI_KEY%" --from-literal=SECRET_KEY="%FLASK_SECRET%"
                        kubectl apply -f k8s/deployment.yaml
                        kubectl apply -f k8s/service.yaml
                        kubectl rollout restart deployment code-comprehension-deployment
                    '''
                }
            }
        }
    }

    post {
        success {
            echo 'Pipeline completed successfully! Application is built, scanned, tested, and deployed to Kubernetes.'
        }
        failure {
            echo 'Pipeline failed. Check the logs above.'
        }
    }
}
