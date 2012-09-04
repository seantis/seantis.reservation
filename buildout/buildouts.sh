#!/bin/bash

if which wget &> /dev/null; then
    wget https://raw.github.com/seantis/seantis.reservation/master/buildout/buildout.cfg -O buildout.cfg
    wget https://raw.github.com/seantis/seantis.reservation/master/buildout/versions.cfg -O versions.cfg
    wget https://raw.github.com/seantis/seantis.reservation/master/buildout/develop.cfg -O develop.cfg
    wget https://raw.github.com/seantis/seantis.reservation/master/buildout/database.cfg.example -O database.cfg.example

fi

if which curl &> /dev/null; then
    curl https://raw.github.com/seantis/seantis.reservation/master/buildout/buildout.cfg -o buildout.cfg
    curl https://raw.github.com/seantis/seantis.reservation/master/buildout/versions.cfg -o versions.cfg
    curl https://raw.github.com/seantis/seantis.reservation/master/buildout/develop.cfg -o develop.cfg  
    curl https://raw.github.com/seantis/seantis.reservation/master/buildout/database.cfg.example -o database.cfg.example
fi

if [ ! -f database.cfg ]; then
    cp database.cfg.example database.cfg
fi