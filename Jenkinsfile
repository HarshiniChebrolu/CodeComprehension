pipeline {
    agent any
    
    environment {
        IMAGE_NAME = "ai-code-reviewer"
    }

    stages {
        stage('Checkout Code') {
            steps {
                // Pulls the latest code from GitHub
                checkout scm
            }
        }

        stage('Build Docker Image') {
            steps {
                echo 'Building Docker image for CodeComprehension...'
                sh "docker build -t ${IMAGE_NAME} ."
            }
        }

        stage('Run Container Smoke Test') {
            steps {
                script {
                    // Pulls the credentials you saved securely in Jenkins
                    withCredentials([
                        string(credentialsId: 'GEMINI_API_KEY', variable: 'GEMINI_API_KEY'),
                        string(credentialsId: 'TAVILY_API_KEY', variable: 'TAVILY_API_KEY')
                    ]) {
                        echo 'Validating container health and execution...'
                        // Runs the container with the injected API keys
                        sh "docker run --rm -d -p 5000:5000 -e GEMINI_API_KEY=${GEMINI_API_KEY} -e TAVILY_API_KEY=${TAVILY_API_KEY} --name code-reviewer-test ${IMAGE_NAME}"
                        sleep 5
                        sh "docker stop code-reviewer-test"
                    }
                }
            }
        }
    }

    post {
        success {
            echo 'Pipeline completed successfully! Docker image is verified.'
        }
        failure {
            echo 'Pipeline failed. Check the logs above.'
        }
    }
}