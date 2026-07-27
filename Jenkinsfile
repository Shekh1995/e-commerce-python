pipeline {
    agent any

    stages {
        stage('Clone Code') {
            steps {
                checkout scm
            }
        }

        stage('Build') {
            steps {
                sh 'python3 -m venv .venv'
                sh '.venv/bin/pip install --upgrade pip'
                sh '.venv/bin/pip install -r requirements.txt'
            }
        }

        stage('Selenium Test') {
            steps {
                sh '.venv/bin/pytest -q'
            }
        }

        stage('Deploy') {
            steps {
                sh '''
                    pkill -f 'gunicorn.*app.main:app' || true
                    JENKINS_NODE_COOKIE=dontKillMe nohup .venv/bin/gunicorn \\
                    --bind 0.0.0.0:8081 app.main:app > app.log 2>&1 &
                '''
            }
        }
    }
}
