# Example script that runs on a local folder. 
# This script is meant to run from project root, 
# and assumes there is a $OPENAI_API_KEY in the .env file 

set -a
source .env
set +a

if [[ "$1" == "--build" ]]; then
  docker rm -f useagent-turbo-test 2>/dev/null
  if [[ "$2" == "--rm-image" ]]; then
    #This will delete the image, but you will loose caching.
    docker image rm -f useagent-turbo:dev 2>/dev/null
  fi
  DOCKER_BUILDKIT=1 docker build --build-arg COMMIT_SHA="$(git rev-parse HEAD)" --ssh default -t useagent-turbo:dev .
fi

TASK_DESC='write a shell file that prints a vegan tiramisu recipe'
MODEL_NAME=openai:gpt-5-mini

rm -rf ./useagent-turbo-tmp
mkdir ./useagent-turbo-tmp
echo "Hi, this is a simple file" > ./useagent-turbo-tmp/README.md
rm -rf ./useagent-turbo-tmp-out
mkdir ./useagent-turbo-tmp-out

docker run --rm \
  --name useagent-turbo-test \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -v ./useagent-turbo-tmp:/input:rw \
  -v ./useagent-turbo-tmp-out:/output:rw \
  useagent-turbo:dev \
  useagent local \
    --model $MODEL_NAME \
    --output-dir /output \
    --project-directory /input \
    --task-description "$TASK_DESC"