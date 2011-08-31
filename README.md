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

Download configs

    curl https://raw.github.com/seantis/seantis.reservation/master/buildout/buildout.cfg -o buildout.cfg
    curl https://raw.github.com/seantis/seantis.reservation/master/buildout/develop.cfg -o develop.cfg
    curl https://raw.github.com/seantis/seantis.reservation/master/buildout/versions.cfg -o versions.cfg
    curl https://raw.github.com/seantis/seantis.reservation/master/buildout/database.cfg.example -o database.cfg

Setup the Database connection by editing the db:engine url in the downloaded database.cfg. Seantis.reservation is developed and tested with sqlite and postgres. If you require another database you can do so by using any of the sqlalchemy supported databases. Note that you may have to install additional database drivers in this case.


Initialize buildout

    buildout init

Setup Database
    

Run buildout

    bin/buildout -c develop.cfg