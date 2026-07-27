pipeline {
    agent any

    stages {
        stage('Clone Code') {
            steps {
                git branch: 'main',
                    url: 'https://github.com/Shekh1995/e-commerce-python.git'
            }
        }

        stage('Build') {
            steps {
                sh '''
                    python3 -m venv .venv
                    .venv/bin/python -m pip install --upgrade pip
                    .venv/bin/python -m pip install -r requirements.txt
                '''
            }
        }

        stage('Test') {
            steps {
                sh '.venv/bin/python -m pytest -q'
            }
        }

        stage('Deploy') {
            steps {
                sh '''
                    echo "Stopping old application"
                    pkill -f 'gunicorn.*app.main:app' || true

                    echo "Starting application on port 8081"
                    JENKINS_NODE_COOKIE=dontKillMe nohup .venv/bin/gunicorn --bind 0.0.0.0:8081 app.main:app > app.log 2>&1 &
                    echo $! > app.pid

                    sleep 3
                    curl -f http://127.0.0.1:8081/health
                '''
            }
        }
    }
}
