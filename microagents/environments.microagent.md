---
name: Environment Info Microagent
version: 1.0.0
agents:
  - DISABLED
triggers:
  - package-manager
  - packagemanager
  - environment
  - virtualization
  - probing
---


This information is meant to help you navigate a new, and unkown, environment with some example commands that might come in handy. 
Do not assume that any of the information here is 100% correct, you should always try to verify it explicitly for your system. 

# Basics - Environment Checking 

**Identify System Type**

```shell
uname -a               # Print system info
uname -s               # Kernel name (e.g., Linux, Darwin)
cat /etc/os-release    # Linux distro and version
```

**Check Present working directory**
```shell
pwd                    # Print working directory
```

**Verify Project Root**
Look for standard files that typically exist at project root: 

```shell
ls -a                  # List all files, including hidden ones
# Check for:
# - README.md
# - LICENSE
# - .git/
# - pyproject.toml (Python)
# - package.json (Node.js)
# - pom.xml (Java Maven)
```

## System Packages 
Each system has its own package manager. 
The package `cowsay` is an example value - please do not install, upgrade, delete or look for it.
Here's how to work with common ones:

**APT**(Debian/Ubuntu)
```shell
apt list --installed                # List all installed packages
apt list --installed | grep python # Filter specific packages

apt-cache policy curl              # Show version and availability
sudo apt update                    # Check package DB
sudo apt install cowsay            # Install example package

**Homebrew [brew]**(MacOS/Linux)

```shell
brew list --versions               # List all installed packages with versions
brew list curl                     # Show version of specific package

brew doctor                        # Check if system is ready
brew install cowsay                # Install package
```

**APK**(Alpine Linux)
```shell
apk info -vv                       # List all packages with version
apk info cowsay                   # Check if a package is installed

apk add cowsay                     # Install package
```

**Pacman**(Arch Linux)
```shell
pacman -Q                         # List installed packages
pacman -Qi cowsay                # Detailed info on specific package

pacman -S cowsay                 # Install package
```

# Project Specifics

## Virtualization Environments 
Virtual environments isolate dependencies and tooling for specific projects, preventing version conflicts.
Depending on the project, it might utilizes virtualization environments. 
It is not your job to introduce new virtualization - but you should be aware and use the projects virtualization. 

### Python 

**virtualenv**
```shell
ls ~/.virtualenvs                  # List (if used via virtualenvwrapper)
source venv/bin/activate          # Activate existing env
deactivate                        # Exit env
```

**poetry**
```shell
poetry env list                   # List all environments
poetry env info --path            # Path to active env
poetry shell                      # Activate env
```

**uv**
```shell
uv venv new                       # Create a new env
uv venv list                      # List environments
uv venv activate <env-name>      # Activate
```

## Package Managers


For each: 
- How to list all packages with version
- Install a new package 
- Upgrade a package

### Python

**Pip**

```shell
pip list                          # List installed packages with versions
pip install requests              # Install a package
pip install --upgrade requests    # Upgrade a package
```
**Anaconda / MiniConda**
```shell
conda list                        # List all packages in current env
conda install numpy               # Install package
conda update numpy                # Upgrade package
```

### Java 

**Maven**
```shell
mvn dependency:list               # List dependencies
mvn install                       # Install project dependencies from pom.xml
mvn versions:display-dependency-updates # See outdated packages
```
**Ant**
Ant does not have a built-in package manager but uses external libraries via XML configuration.
```
ant -version                      # Check if Ant is installed
ant                               # Run build script from `build.xml`
# Dependencies typically downloaded via Ivy or manually included
```
