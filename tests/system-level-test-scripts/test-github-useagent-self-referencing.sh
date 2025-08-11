# We had the strange case that for some datapoints, USEAgent tries to test itself instead of the datapoint. 
# Usually the trajectory still starts normally in the right directory, just moves somewhere.
# Its hard to pin-point but that happens somewhere between probing and search agent. 

# To run the script, you need a valid API key in .env, as well as docker up and running.

set -a
source .env
set +a

if [[ "$1" == "--build" ]]; then
  docker rm -f useagent-turbo-test 2>/dev/null
  if [[ "$2" == "--rm-image" ]]; then
    #This will delete the image, but you will loose caching.
    docker image rm -f useagent-turbo:dev 2>/dev/null
  fi
  DOCKER_BUILDKIT=1 docker build --ssh default -t useagent-turbo:dev .
fi


REPO_URL=https://github.com/Activiti/Activiti.git
MODEL_NAME=google-gla:gemini-2.5-flash

mkdir ./tmp
cat > ./tmp/task.md <<'EOF'
You are a software engineering and now there is a project under current working directory. Your task is to produce a bash script named run_test.sh that can build the project and run the tests for this project.
You are working on a ubuntu 22.04 platform. In case some projects require additional dependency, you can choose to install OS-level dependency as well.
You need to always figure out what is the primary programming language this project is using, what build system does this project use and what testing framework in this project.
You should execute your bash script to observe the results. If you think the output shows tests passed, you can terminate the workflow.
EOF


docker run --rm \
  --name useagent-turbo-test \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  -v ./tmp:/task:rw \
  -v ./useagent-turbo-tmp-out:/output:rw \
  useagent-turbo:dev \
  /bin/bash -c "PYTHONPATH=. uv run python useagent/main.py github --model $MODEL_NAME --task-file /task/task.md --repo-url $REPO_URL  --output-dir /output"
