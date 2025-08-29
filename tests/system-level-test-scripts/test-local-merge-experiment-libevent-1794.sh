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

IMPORTANT: You are in the working directly and on the base branch now, the feature branch name is called `master`.

In case you need, the `master`  is from `https://github.com/vaerksted/libevent.git`

# Dos and Do nots 
- Do use `git` tools to create your merge and report the diff. Do not try to generate a string looking like a diff. 
- Consider executing (relevant) tests before performing the merge to capture pre-merge behavior. 
- Do not create a new branch for the merge. You are supposed to determine the main branch, and merge the feature branch into this main branch. 
- Do not make more than one commit. You must perform all tasks in one commit, or squash multiple commits if they were necessary. 
- Do not attempt to fix all issues and problems. Only aim to address errors and mistakes that seem related to your merge commit.
- You must use non-interactive commands.

# The Pull Bequest Description from the developer

@azat This pull modifes the Python script. $ sed -n 4p libevent/event_rpcgen.py # Copyright c 2007-2012 Niels Provos and Nick Mathewson $ Dont change commit messages. $ grep -n emiting libevent/ChangeLog-2.0 1266: o Add generic implementations for parsing and emiting IPv6 addresses on platforms that do not have inet_ntop and/or inet_pton. $ grep -n grammer libevent/ChangeLog-2.1 536: o Bugfix fix grammer error 3a4d249 ufo2243 $ grep -n looksups libevent/ChangeLog-2.0 879: o Allow http connections to use evdns for hostname looksups. c698b77 $ grep -n redinition libevent/ChangeLog-2.1 11: o Fix _FILE_OFFSET_BITS redinition solaris/autotools 336f3b11 Azat Khuzhin $ grep -n reseting libevent/ChangeLog 77: o Explicitly call SSL_clear when reseting the fd. #498 c6c74ce2 David Benjamin $ grep -n retrasmitting libevent/ChangeLog-2.1 490: o evdns: fail ns after we are failing/retrasmitting request 97c750d Azat Khuzhin $ grep -n runned libevent/ChangeLog 181: o Fix base unlocking in event_del if event_base_set runned in another thread 08a0d366 Azat Khuzhin $ grep -n separatelly libevent/ChangeLog-2.1 216: o test/http: cover NS timed out during request cancellations separatelly 0c343af Azat Khuzhin $ grep -n separte libevent/ChangeLog-2.0 728: o Add a comment to explain why evdns_request is now separte from request ceefbe8 $ grep -n soure libevent/ChangeLog-2.0 952: o Add a check to make soure our EVUTIL_AI flags do not conflict with the native ones c18490e $ grep -n spoted libevent/ChangeLog-2.0 906: o Fix two use-after-free bugs in unit tests spoted by lock debugging d84d838 $ grep -n ubunty libevent/ChangeLog-2.1 404: o cmake: require 3.1 only for win32 to make it work under ubunty precise 87f7238 Azat Khuzhin $ grep -n unconditioally libevent/ChangeLog-2.1 159: o http: set fd to -1 unconditioally, to avoid leaking of DNS requests 7a4b472 Azat Khuzhin $ grep -n workth libevent/ChangeLog 92: o Make http-connect workth with pproxy 462f2e97 Azat Khuzhin $ 
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
  -v ~/playground/libevent-1794:/input:rw \
  -v ./useagent-turbo-tmp-out:/output:rw \
  -v ./useagent-turbo-tmp-out/project:/tmp/working_dir:rw \
  useagent-turbo:dev \
  useagent local \
    --model $MODEL_NAME \
    --output-dir /output \
    --project-directory /input \
    --task-file /task/task.md