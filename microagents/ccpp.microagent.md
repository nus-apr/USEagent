---
name: Environment Info Microagent
version: 1.0.0
agents:
  - PROBE
triggers:
  - cmake
  - cpp
  - c++
  - gcc
  - build-essentials
---

# C/C++ Build Tools on Ubuntu 24 (Docker)


## 1. Identifying Build Systems

| Tool        | Purpose | How to Detect in Project |
|-------------|---------|--------------------------|
| **make**    | Runs builds via `Makefile`. | Look for `Makefile` in root. |
| **cmake**   | Generates build scripts for various systems. | Look for `CMakeLists.txt`. |
| **gcc/g++** | C/C++ compilers. | Needed for compiling C/C++ directly or by other tools. |
| **build-essential** | Meta-package with GCC, G++, make, etc. | Install if unsure—covers most needs. |

---

## 2. Installing Build Tools

```bash
apt update
apt install -y build-essential cmake
```

`build-essential` → gcc, g++, make, headers
`cmake` → only needed if `CMakeLists.txt` present

## 3. Usage Examples
Compile C
```bash
gcc main.c -o app
```
Compile C++
```bash
g++ main.cpp -o app
```


Build with make
```bash
make
```
Build with cmake
```bash
cmake -S . -B build
cmake --build build
```
## 4. Determining What’s Needed
Check for files:

`Makefile` → make
`CMakeLists.txt` → cmake
`.c/.cpp only` → direct gcc/g++

Check docs: `README.md`, `INSTALL.md`

Fallback: Install build-essential cmake

## 5. Finding Missing Libraries
Search for development packages:

```bash
apt search lib<name>-dev
```

Using pkg-config:

```bash
pkg-config --cflags --libs <name>
```

From linker errors:

If you see undefined reference to 'png_create_read_struct' → likely `libpng-dev`
If you see cannot find `-lssl` → install `libssl-dev`

## 6. Common Errors & Fixes

| Error                                            | Cause                   | Fix                                              |
| ------------------------------------------------ | ----------------------- | ------------------------------------------------ |
| `make: command not found`                        | Missing make            | `apt install make` (or `build-essential`)        |
| `gcc: command not found`                         | Missing gcc             | `apt install build-essential`                    |
| `cmake: command not found`                       | Missing cmake           | `apt install cmake`                              |
| `fatal error: <xxx>.h: No such file`             | Missing headers         | Install dev package (`apt search xxx-dev`)       |
| `undefined reference to ...`                     | Missing library at link | Add `-l<libname>` to gcc/g++                     |
| `cannot find -l<libname>`                        | Library not installed   | `apt install lib<name>-dev`                      |
| `pkg-config: command not found`                  | Missing pkg-config      | `apt install pkg-config`                         |
| `Package <name> was not found` (from pkg-config) | Missing dependency      | `apt search <name>` then install `lib<name>-dev` |
