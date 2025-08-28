# Local Task to check if we can mount in and out the working directory. 
# Initially we had some issues in the setup stage, because it would not expect the working directory to exist. 
# But if we mount it, it gets created, which lead to an error earlier. 

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


REPO_URL=https://github.com/ansible/ansible.git
MODEL_NAME=google-gla:gemini-2.5-flash

mkdir ./tmp
cat > ./tmp/task.md <<'EOF'
You are a software engineer and I want a file called run_tests.sh (at root of your directory) that prints 'hello world'. 
EOF

rm -rf ./useagent-turbo-tmp
mkdir ./useagent-turbo-tmp
git clone $REPO_URL ./useagent-turbo-tmp
rm -rf ./useagent-turbo-tmp-out
mkdir ./useagent-turbo-tmp-out


docker run --rm \
  --name useagent-turbo-test \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -v ./tmp:/task:rw \
  -v ./useagent-turbo-tmp:/input:rw \
  -v ./useagent-turbo-tmp-out:/output:rw \
  -v ./useagent-turbo-tmp-out/project:/tmp/working_dir:rw \
  useagent-turbo:dev \
  useagent local \
    --model $MODEL_NAME \
    --output-dir /output \
    --project-directory /input \
    --task-file /task/task.md