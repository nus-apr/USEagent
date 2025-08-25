# Example script that runs on a github repository and is prompted to perform an action. 
# This script is meant to run from project root, 
# and assumes there is a $GEMINI_API_KEY in the .env file 
# Use --build to force a rebuild.

set -a
source .env
set +a

if [[ "$1" == "--build" ]]; then
  docker rm -f useagent-turbo-test 2>/dev/null
  docker image rm -f useagent-turbo:dev 2>/dev/null
  DOCKER_BUILDKIT=1 docker build --ssh default -t useagent-turbo:dev .
fi


TASK_DESC='Please use git to checkout the initial commit of the repository.'
REPO_URL=https://github.com/octocat/Hello-World.git
MODEL_NAME=google-gla:gemini-2.5-flash

docker run --rm \
  --name useagent-turbo-test \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  -v ./useagent-turbo-tmp-out:/output \
  useagent-turbo:dev \
  useagent github \
    --model $MODEL_NAME \
    --repo-url $REPO_URL \
    --output-dir /output \
    --output-type action \
    --task-description "$TASK_DESC"
