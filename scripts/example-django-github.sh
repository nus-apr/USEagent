# Example script that runs on a github repository. 
# The chosen project is django, this script is meant to see the probing agent receive a correct command. 
# This script is meant to run from project root, 
# and assumes there is a $GEMINI_API_KEY in the .env file 
# Use --build to force a rebuild.

set -a
source .env
set +a

task_desc='I need a new shell file my_test.sh that will run all of the projects unit tests and sets up an virtual environment before if necessary. DO NOT give me placeholders. There is a project specific way to run the tests, and I want you to discover it. Do not leave tasks to me.'
repo_url=https://github.com/django/django.git 

if [[ "$1" == "--build" ]]; then
  docker rm -f useagent-turbo-test 2>/dev/null
  docker image rm -f useagent-turbo:dev 2>/dev/null
  DOCKER_BUILDKIT=1 docker build --ssh default -t useagent-turbo:dev .
fi

docker run --rm \
  --name useagent-turbo-test \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  -v ./useagent-turbo-tmp-out:/output \
  useagent-turbo:dev \
  /bin/bash -c "PYTHONPATH=. uv run python useagent/main.py github --model google-gla:gemini-2.0-flash --task-description '$task_desc' --repo-url $repo_url --output-dir /output"
