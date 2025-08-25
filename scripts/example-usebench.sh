# Example script that runs on a example usebench task (swe_django__django-10914). 
# This script is meant to run from project root, 
# and assumes there is a $GEMINI_API_KEY in the .env file 
# Use --build to force a rebuild.

set -a
source .env
set +a

TASK_ID=swe_django__django-10914
USEBENCH_BASE_IMAGE=usebench.sweb.eval.x86_64.django__django-10914
MODEL_NAME=google-gla:gemini-2.5-flash

if [[ "$1" == "--build" ]]; then
  docker rm -f useagent-turbo-test 2>/dev/null
  if [[ "$2" == "--rm-image" ]]; then
    #This will delete the image, but you will loose caching.
    docker image rm -f useagent-turbo:dev 2>/dev/null
  fi
  DOCKER_BUILDKIT=1 docker build --build-arg BASE_IMAGE=$USEBENCH_BASE_IMAGE --ssh default -t useagent-turbo:dev .
fi

docker run --rm \
  --name useagent-turbo-test \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  useagent-turbo:dev \
  useagent usebench --model $MODEL_NAME --task-id $TASK_ID --output-dir /output"
