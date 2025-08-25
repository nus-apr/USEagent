# The useagent can struggle by its tooling to 'just execute a script'
# This lead to weird behavior where e.g. the vcs agent was asked to execute a script and it refused. 
# This test tries a different prompt to see if things can be done slightly different. 

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


#REPO_URL=https://github.com/google/guava.git
REPO_URL=https://github.com/ansible/ansible.git
MODEL_NAME=google-gla:gemini-2.0-flash

mkdir ./tmp
cat > ./tmp/task.md <<'EOF'
You are a software engineering and now there is a project under current working directory. Your task is to produce a bash script named run_test.sh that can build the project and run the tests for this project.
You are working on a ubuntu. In case some projects require additional dependency, you can choose to install OS-level dependency as well.
You need to always figure out what is the primary programming language this project is using, what build system does this project use and what testing framework in this project.
Make sure to investigate and verify the commands you introduce into `run_tests.sh`. 
Once you have successfully created a file, report with a git diff of the change that I can use as a patch to introduce this `run_tests.sh` to a newly checked out version of the repository. 
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
