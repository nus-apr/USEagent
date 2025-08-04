# Example script that runs the merges required as per CI Agents project. 
# Assumes there is a correctly set up project under ~/langchain-example
# This script is meant to run from project root, 
# and assumes there is a $GEMINI_API_KEY in the .env file 

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
PROJECT_DIR=~/langchain-example

cat > ~/langchain-example/task.md <<'EOF'
You are a software engineer. Now your teammates have developed a new feature (in another branch named `fix/docstring_base_model`. Now, you want to merge it to the branch `master` carefully. It's important to ensure this merge will not introduce any new failed tests. Please complete this task by constructing environments, run test suites and merge the feature branch. Then conduct testing again. 
Thus, the workflow is: 1. build the environment, 2. run the test suite, 3. code reivew for the new changes. 4, merge the feature into the base branch. 5. Run the test suite again after merge.'
EOF


docker run --rm \
  --name useagent-turbo-test \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  -v $PROJECT_DIR:/input:rw \
  -v ./useagent-turbo-tmp-out:/output:rw \
  useagent-turbo:dev \
  /bin/bash -c "PYTHONPATH=. uv run python useagent/main.py local --model google-gla:gemini-2.0-flash --task-file /input/task.md --output-dir /output --project-directory /input"
