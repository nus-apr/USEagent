# Example how we are meant to run for the CI-CD Project, exact same prompt etc. 
# Prompt as of 2025-08-15 

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


REPO_URL=https://github.com/google/guava.git
#REPO_URL=https://github.com/ansible/ansible.git
#REPO_URL=https://github.com/ccache/ccache.git
#REPO_URL=https://github.com/json-c/json-c.git
MODEL_NAME=google-gla:gemini-2.5-flash

mkdir ./tmp
cat > ./tmp/task.md <<'EOF'
You are a DevOps software engineering and now there is an project under current working directory. Your task is to produce a bash script named `run_test.sh` that can build the project and run the tests for this project.

# Default Environment You have
You are working on a ubuntu 24.04 platform (using a default Docker image) on a CPU sever (No any GPUs available). It also means there are limited software/libraries installed. 
Since this is an isolated docker container, so you have the root level permission to run any commands.

# Your Output
You need to produce a test script (bash script) named `run_test.sh`. 

# What does your script do
- Your script should run all the test suites. If tests are not applicable the base environment, you can choose to skip some.
- Your script should be self-contained and install all necessary dependencies. 
- If there are dependencies that are crucial to the project, and you see them in your existing environment, please still list them amongst the to-install-dependencies in your script. 
- We will run this script in fresh environment.

# DO & DO NOT
- Do verify commands you use in the script, e.g. by executing them before producing your final bash script. You should execute your bash script to observe the results. If you think the output shows tests passed, you can terminate the workflow.
- You can install necessary dependencies in this environment but include them into your final bash script.
- Do not hallucinate any commands or actions
- YOU MUST use non-interactive commands.
- Do add set -vxE at the top of your script, for easier debugging and proofreading the script execution
EOF


docker run --rm \
  --name useagent-turbo-test \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -v ./tmp:/task:rw \
  -v ./useagent-turbo-tmp-out:/output:rw \
  useagent-turbo:dev \
  useagent github \
    --model $MODEL_NAME \
    --output-dir /output \
    --repo-url $REPO_URL \
    --task-file /task/task.md
