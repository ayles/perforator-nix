#! /usr/bin/env nix-shell
#! nix-shell -i python3 -p python3 common-updater-scripts
import base64
import collections
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.request


REGISTRY_ENDPOINT = "https://devtools-registry.s3.yandex.net"

# Parameters below are hard-coded, it only takes moving them to the script arguments and it will be possible to reuse it for packaging anything built with ya.
known_platforms = [
    ("x86_64-linux", "linux"),
]

repo = "https://github.com/yandex/perforator"

package = "perforator"


def remote_sha256(url):
    remote = urllib.request.urlopen(url)
    hash = hashlib.sha256()

    while True:
        data = remote.read(4096)

        if not data:
            break

        hash.update(data)

    return base64.b64encode(hash.digest()).decode()


def postprocess_sbr(sbr, name=None):
    url = f"{REGISTRY_ENDPOINT}/{sbr}"

    return {
        "url": url,
        "hash": f"sha256-{remote_sha256(url)}",
    } | ({"name": name} if name is not None else {})


def postprocess_resources(entries, platform):
    out = dict()

    def add_resource(resource, name):
        if not resource.startswith("sbr:"):
            return

        sbr = resource.removeprefix("sbr:")
        out[sbr] = postprocess_sbr(sbr, name)

    for entry in entries:
        if "resource" in entry:
            add_resource(entry["resource"], entry.get("pattern"))
        elif "resources" in entry:
            for platform_entry in entry["resources"]:
                if platform_entry["platform"].lower() == platform:
                    add_resource(platform_entry["resource"], entry.get("pattern"))

    return out


if __name__ == '__main__':
    resources = collections.defaultdict(dict)

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "clone", repo, tmp], check=True)

        entries = json.loads(subprocess.run(
            [os.path.join(tmp, "ya"), "make", "-G", "-j0"] + sys.argv[1:],
            cwd=tmp,
            check=True,
            stdout=subprocess.PIPE
        ).stdout)["conf"]["resources"]

        entries.append({
            "resources": [{
                "platform": ya_platform,
                "resource": subprocess.run(
                    [os.path.join(tmp, "ya"), "tool", "ymake", "--platform", ya_platform, "--get-resource-id"],
                    cwd=tmp,
                    check=True,
                    stdout=subprocess.PIPE
                ).stdout.decode().splitlines()[0]
            } for _, ya_platform in known_platforms]
        })

        with open(os.path.join(tmp, "ya"), 'r', encoding='utf-8') as f:
            ya_text = f.read()
            ya_map_text = ya_text[ya_text.index("PLATFORM_MAP = ")+15:ya_text.index("# End of mapping")]
            ya_map = eval(ya_map_text)

            for platform, ya_platform in known_platforms:
                resources[platform]["ya"] = postprocess_sbr(ya_map["data"][ya_platform]["urls"][0].removeprefix(f"{REGISTRY_ENDPOINT}/"), "ya")


    for platform, ya_platform in known_platforms:
        resources[platform]["tools"] = postprocess_resources(entries, ya_platform)


    with open(os.path.join("nix", "resources.json"), 'w', encoding='utf-8') as f:
        json.dump(resources, f, indent=4)


    version = subprocess.run(
        f"list-git-tags --url={repo} | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+' | sort -V | tail -n1",
        shell=True,
        check=True,
        stdout=subprocess.PIPE
    ).stdout.decode().splitlines()[0]

    subprocess.run(["update-source-version", package, version], check=True)

