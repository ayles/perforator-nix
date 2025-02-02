{
  stdenvNoCC,
  fetchurl,
  lib,
  buildFHSEnv,
  runCommand,
  writeShellScript,
  fetchFromGitHub,
}:
let
  fetch =
    { url, hash }:
    let
      src = fetchurl { inherit url hash; };
    in
    runCommand "unpack" { } ''
      mkdir -p $out
      tar -xf ${src} -C $out
    '';

  resources = (builtins.fromJSON (builtins.readFile ./resources.json)).${stdenvNoCC.system};

  ya = fetch resources.ya;

  tools = lib.mapAttrs (k: v: fetch v) resources.tools;

  targets = [
    "perforator/cmd/agent"
    "perforator/cmd/cli"
    "perforator/cmd/gc"
    "perforator/cmd/migrate"
    "perforator/cmd/offline_processing"
    "perforator/cmd/proxy"
    "perforator/cmd/storage"
    # "perforator/cmd/web"
  ];
in
stdenvNoCC.mkDerivation rec {
  pname = "perforator";
  version = "v0.0.1";

  src = fetchFromGitHub {
    owner = "yandex";
    repo = "perforator";
    rev = version;
    sha256 = "sha256-VyMpuqMvxEB654fd9rY3pT4PHXUj/GhxTv8mRiV2YC4=";
  };

  configurePhase =
    ''
      export YA_CACHE_DIR=.ya
      mkdir -p $YA_CACHE_DIR/tools/v3
    ''
    + lib.concatStrings (
      lib.mapAttrsToList (k: v: ''
        mkdir -p $YA_CACHE_DIR/tools/v3/${k}
        cp -sr ${v}/* $YA_CACHE_DIR/tools/v3/${k}
        # Some kind of version that is required to be present for the cache to work
        echo -n "2" > $YA_CACHE_DIR/tools/v3/${k}/INSTALLED
      '') tools
    );

  buildPhase = ''
    ${
      buildFHSEnv {
        name = "fhs";
        targetPkgs = pkgs: with pkgs; [ libxcrypt-legacy ];
      }
    }/bin/fhs ${writeShellScript "build" ''
      # There is a way to hack it with tools cache (dir .ya/tools/v4) enabled, but it will require one more tool and additional commands to populate tc db
      ${ya}/ya-bin make -T --noya-tc -j $NIX_BUILD_CORES -o ./result ${lib.concatStringsSep " " targets}
    ''}
  '';

  installPhase =
    ''
      mkdir -p $out/bin
    ''
    + lib.concatStrings (
      map (target: ''
        cp ./result/${target}/* $out/bin/
      '') targets
    );

  passthru.updateScript = [ ./update.py ] ++ targets;
}
