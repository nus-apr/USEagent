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

MODEL_NAME=google-gla:gemini-2.5-flash

mkdir ./tmp
cat > ./tmp/task.md <<'EOF'
# Role
You are given a software development task to perform a `merge` of a feature in your current directory. Your task is to identify the main and feature branch and perform a successful merge commit.


If there is a merge conflict, handle the merge commit appropriately under the assumption that all features of the incoming commit are necessary and wanted. 
Try to keep all features and concepts of the main branch intact while resolving merge conflicts, and only deprecate or remove those that are directly conflicting with the incoming features. 

Changes and decisions made by you must be motivated by test-results.


# Default Environment and your current setup

- You are working on a ubuntu 24.04 platform (using a default Docker image) on a CPU sever (No any GPUs available and Internet is accessible). 

Since this is an isolated docker container, you have the root level permission to run any commands.

IMPORTANT: You are in the working directly and on the base branch now, the feature branch name is called `menu`.

In case you need, the `menu`  is from `https://github.com/guidocella/mpv.git`

# Dos and Do nots 
- Do use `git` tools to create your merge and report the diff. Do not try to generate a string looking like a diff. 
- Consider executing (relevant) tests before performing the merge to capture pre-merge behavior. 
- Do not create a new branch for the merge. You are supposed to determine the main branch, and merge the feature branch into this main branch. 
- Do not make more than one commit. You must perform all tasks in one commit, or squash multiple commits if they were necessary. 
- Do not attempt to fix all issues and problems. Only aim to address errors and mistakes that seem related to your merge commit.
- You must use non-interactive commands.

# The Pull Bequest Description from the developer

This implements a ASS context menu to be used on platforms other than Windows. The select script message will allow selecting an item with a single click when releasing a mouse button, like in native context menus. This is mainly useful to cycle pause with one click.
#  Your Task and Output
- perform the merge by producing the resulting merge commit; The merge commit must be a valid `git diff`. 
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
  -v ~/playground/mpv-16726:/input:rw \
  -v ./useagent-turbo-tmp-out:/output:rw \
  -v ./useagent-turbo-tmp-out/project:/tmp/working_dir:rw \
  useagent-turbo:dev \
  useagent local \
    --model $MODEL_NAME \
    --output-dir /output \
    --project-directory /input \
    --task-file /task/task.md