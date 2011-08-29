Setup Developer Environment
===========================

Create your development directory

    mkdir seantis.reservation
    cd seantis.reservation

Initalize your virtual environment

    virtualenv . --no-site-packages --p python2.6
    . bin/activate

Get zc.buildout and zopeskel

    pip install zc.buildout
    pip install zopeskel

Download buildout.cfg and develop.cfg

    curl https://raw.github.com/seantis/seantis.reservation/master/buildout/buildout.cfg -o buildout.cfg
    curl https://raw.github.com/seantis/seantis.reservation/master/buildout/develop.cfg -o develop.cfg

Initialize buildout

    buildout init

Run buildout

    bin/buildout -c develop.cfg