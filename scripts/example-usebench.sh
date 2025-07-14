# Example script that runs on a example usebench task (swe_django__django-10914). 
# This script is meant to run from project root, 
# and assumes there is a $GEMINI_API_KEY in the .env file 
# Use --build to force a rebuild.

set -a
source .env
set +a

if [[ "$1" == "--build" ]]; then
  docker rm -f useagent-turbo-test 2>/dev/null
  docker image rm -f useagent-turbo:dev 2>/dev/null
    DOCKER_BUILDKIT=1 docker build --build-arg BASE_IMAGE=usebench.sweb.eval.x86_64.django__django-10914 --ssh default -t useagent-turbo:dev .
fi

docker run --rm \
  --name useagent-turbo-test \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  useagent-turbo:dev \
  /bin/bash -c "PYTHONPATH=. uv run python useagent/main.py usebench --model google-gla:gemini-2.0-flash --task-id swe_django__django-10914 --output-dir /output"
