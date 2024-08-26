#!/bin/bash
# Build an Icegrams release and upload it to PyPi
if [ "$1" = "" ]; then
   echo "Version name argument missing"
   exit 1
fi
echo "Upload a new Icegrams version:" "$1"
# Fix permission bits
chmod -x src/icegrams/*.py
chmod -x src/icegrams/*.cpp
chmod -x src/icegrams/*.h
chmod -x src/icegrams/resources/*
# Create the base source distribution
rm -rf build/*
python setup.py sdist
# Create the binary wheels
source wheels.sh
# Upload the new release
twine upload dist/icegrams-$1*
echo "Upload of" "$1" "done"
