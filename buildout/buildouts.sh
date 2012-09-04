#!/bin/bash

if which wget &> /dev/null; then
    wget https://raw.github.com/seantis/seantis.reservation/master/buildout/buildout.cfg -O buildout.cfg
    wget https://raw.github.com/seantis/seantis.reservation/master/buildout/versions.cfg -O versions.cfg
    wget https://raw.github.com/seantis/seantis.reservation/master/buildout/develop.cfg -O develop.cfg
fi

if which curl &> /dev/null; then
    curl https://raw.github.com/seantis/seantis.reservation/master/buildout/buildout.cfg -o buildout.cfg
    curl https://raw.github.com/seantis/seantis.reservation/master/buildout/versions.cfg -o versions.cfg
    curl https://raw.github.com/seantis/seantis.reservation/master/buildout/develop.cfg -o develop.cfg  
fi