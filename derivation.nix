{ lib, python3Packages }:
with python3Packages;
buildPythonPackage {
  pname = "riley";
  version = "0.1.0";

  nativeBuildInputs = [ setuptools_scm ];
  propagatedBuildInputs = [ ];

  doCheck = false;

  src = ./.;
}
