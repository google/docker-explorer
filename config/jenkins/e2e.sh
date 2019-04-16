#!/bin/bash

set -e

TMP_MOUNTPOINT="$(mktemp -d)"

# Installs necessary packages, as well as the code to test
function install_packages {
  sudo apt -y install docker.io jq python-setuptools
  git clone https://github.com/google/docker-explorer || echo 'Already cloned'
  cd docker-explorer
  sudo python setup.py install
}

# Checks a string against another, fails if they don't match.
# Args:
#   A message for the current text, as string,
#   The expected result, as string,
#   The result to check.
function assert_equal {
  local message="${1}"
  local expected="${2}"
  local result="${3}"

  echo "${message}"
  if [[ "${expected}" != "${result}" ]]; then
      echo "Assert ERROR - Got: \"${result}\""
      return 1
  fi
}

# Cleans up the environment
function cleanup {
  umount "${TMP_MOUNTPOINT}" || true
  rm -rf "${TMP_MOUNTPOINT}"

  # Killing all containers
  docker kill $(docker ps -q) || true

  rm -rf /etc/docker
  apt -y remove --purge docker.io
  rm -rf /var/lib/docker
}

# Starts a detached container
function start_docker {
    docker run -d wordpress:latest
}

# Tests that docker-explorer detects one running container
function test_containers_nb {
  local result
  result="$(de.py -r /var/lib/docker list running_containers | jq '. | length' )"
  assert_equal "Number of containers" "1" "${result}"
  return 0
}

# Tests that docker-explorer detects the container name
function test_container_name {
  local result
  result="$(de.py -r /var/lib/docker list running_containers | jq '.[0]["image_name"]' )"
  assert_equal "First container name" \
    "\"wordpress:latest\"" $result
  return 0
}

# Checks that docker-explorer can mount a container filesystem and find
# relevant files
function test_container_mount {
  local container_id
  local fake_bad_path
  local fake_bad_content
  local content

  container_id="$(de.py -r /var/lib/docker list running_containers | jq '.[0]["container_id"]' | cut -d '"' -f 2)"
  echo "Trying to mount container ID ${container_id} on ${TMP_MOUNTPOINT}"
  de.py -r /var/lib/docker mount "${container_id}" "${TMP_MOUNTPOINT}"

  fake_bad_path="/tmp/definitely_bad"
  fake_bad_content="NOT A MALWARE"
  echo "Adding bad file in ${fake_bad_path}"
  docker exec -i "${container_id}" sh -c "echo '${fake_bad_content}' > '${fake_bad_path}'"
  path_to_file="${TMP_MOUNTPOINT}/${fake_bad_path}"
  if [[ -f "${path_to_file}" ]]; then
    content=$(cat "${path_to_file}")
    assert_equal "bad file has expected content" "${fake_bad_content}" "${content}"
  else
    echo "Didn't find expected bad file at ${path_to_file}"
    return 1
  fi
  return 0
}

# Runs docker-explorer tests
function run_de_tests {
  test_containers_nb
  test_container_name
  test_container_mount
  echo "ALL TESTS PASS!"
  return 0
}

function main {
  install_packages
  start_docker
  run_de_tests
  cleanup
  return 0
}

main
