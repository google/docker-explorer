#!/bin/bash

set -e

TMP_MOUNTPOINT="$(mktemp -d)"

function install_packages {
  sudo apt -y install docker.io jq python-setuptools
  git clone https://github.com/google/docker-explorer || echo 'Already cloned'
  cd docker-explorer
  sudo python setup.py install
}

function assert_equal {
  local message="${1}"
  local expected="${2}"
  local result="${3}"

  echo "${message}"
  if [[ "${expected}" == "${result}" ]]; then
      echo "'${expected}' == '${result}'"
      return 0
  else
      echo "'${expected}' != '${result}'"
      return 1
  fi
}

function cleanup {
  umount "${TMP_MOUNTPOINT}" || true
  rm -rf "${TMP_MOUNTPOINT}"

  # Killing all containers
  docker kill $(docker ps -q) || true

  apt -y remove --purge docker.io
  rm -rf /etc/docker
  rm -rf /var/lib/docker
}

function setup_docker {
    docker run -d wordpress:latest
}

function run_de {
  local result
  result="$(de.py -r /var/lib/docker list running_containers | jq '. | length' )"
  assert_equal "Number of containers should be 1" "1" "${result}"

  result="$(de.py -r /var/lib/docker list running_containers | jq '.[0]["image_name"]' )"
  assert_equal "First container name should be wordpress:latest" "\"wordpress:latest\"" $result

  container_id="$(de.py -r /var/lib/docker list running_containers | jq '.[0]["container_id"]'  | cut -d '"' -f 2)"
  echo "Trying to mount container ID ${container_id} on ${TMP_MOUNTPOINT}"
  de.py -r /var/lib/docker mount "${container_id}" "${TMP_MOUNTPOINT}"

  fake_bad_path="/tmp/definitely_bad"
  fake_bad_content="NOT A MALWARE"
  echo "Adding 'bad file' in ${fake_bad_path}"
  docker exec -i -t "${container_id}" sh -c "echo '${fake_bad_content}' > '${fake_bad_path}'"
  path_to_file="${TMP_MOUNTPOINT}/${fake_bad_path}"
  if [[ -f "${path_to_file}" ]]; then
    content=$(cat "${path_to_file}")
    assert_equal "bad file has expected content" "${fake_bad_content}" "${content}"
  else
    echo "Didn't find expected bad file at ${path_to_file}"
    return 1
  fi
  echo "ALL TESTS PASS!"
}

function main {
  install_packages
  setup_docker
  run_de
  cleanup
}

trap "{
    cleanup
}" EXIT

trap "{
    exit 1
}" INT

main
