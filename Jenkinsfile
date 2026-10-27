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

        stage('Run Container Smoke Test') {
            steps {
                script {
                    withCredentials([
                        string(credentialsId: 'GEMINI_API_KEY', variable: 'GEMINI_API_KEY'),
                        string(credentialsId: 'OPENAI_API_KEY', variable: 'OPENAI_API_KEY')
                    ]) {
                        echo 'Validating container health and execution...'
                        // Use bat and Windows-friendly syntax for running and sleeping
                        bat "docker run --rm -d -p 5000:5000 -e GEMINI_API_KEY=${GEMINI_API_KEY} -e OPENAI_API_KEY=${OPENAI_API_KEY} --name code-reviewer-test ${IMAGE_NAME}"
                        bat "timeout /t 5 /nobreak > nul"
                        bat "docker stop code-reviewer-test"
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
