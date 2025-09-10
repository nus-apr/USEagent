# Example script that runs on a example swebench task (sphinx-doc__sphinx-8265). 
# This script is meant to run from project root, 
# and assumes there is a $GEMINI_API_KEY in the .env file 
# Use --build to force a rebuild, use --rm-image for a complete clean slate rebuild (VERY SLOW).

set -a
source ./.env
set +a

TASK_ID=sphinx-doc__sphinx-8265
#MODEL_NAME=google-gla:gemini-2.5-flash
MODEL_NAME=openai:gpt-5-mini

if [[ "$1" == "--build" ]]; then
  docker rm -f useagent-turbo-test 2>/dev/null
  if [[ "$2" == "--rm-image" ]]; then
    #This will delete the image, but you will loose caching.
    docker image rm -f useagent-turbo:dev 2>/dev/null
  fi
  DOCKER_BUILDKIT=1 docker build --ssh default -t useagent-turbo:dev .
fi

docker run --rm \
  --name useagent-turbo-test \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -v ./useagent-turbo-tmp-out:/output \
  useagent-turbo:dev \
  useagent swebench --model $MODEL_NAME --instance-id $TASK_ID --output-dir /output
